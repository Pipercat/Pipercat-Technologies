"""First-setup wizard: timezone, location, and initial rooms
(S1V2-02-030). "Owner, Haus" (the household + its first owner) are
S1V2-02-028's `DevicePairingService.claim_device()` - this service is
what a resumed wizard calls afterward for the remaining steps.

"Standort nur in minimal erforderlicher Genauigkeit speichern":
`set_location_and_timezone()` rounds latitude/longitude to 2 decimal
places (~1.1 km) before persisting - enough for timezone/sunrise-sunset/
weather-by-region purposes, never street-address-level precision.

"Teilabbruch wiederaufnehmbar, aber kein halb autorisiertes System
erzeugen": each step is its own atomic DB transaction (never partially
applied - the same pattern `DevicePairingService`/`RoomService` already
use), and `get_progress()` reports the *actual* current state (current
timezone/location, the rooms that already exist, whether the wizard was
ever marked complete) rather than inferring completion from a value
happening to differ from its default - a resumed client sees real data,
never a guess. `add_rooms()` skips any name that already exists for this
household (case-insensitive) so retrying the same request after a
network hiccup never creates duplicates. `complete_setup()` is itself
idempotent (`HouseholdRepository.mark_setup_completed()`) - calling it
again is a no-op, never an error.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.audit import AuditRecorder
from app.authorization import Actor, require_permission, require_same_household
from app.repositories.records import RoomRecord
from app.uow import UnitOfWork

_LOCATION_DECIMAL_PLACES = 2  # ~1.1 km - "minimal erforderliche Genauigkeit"


class HouseholdNotFoundError(ValueError):
    def __init__(self, household_id: str) -> None:
        super().__init__(f"Household '{household_id}' does not exist.")
        self.household_id = household_id


@dataclass(frozen=True)
class WizardProgress:
    timezone: str
    latitude: float | None
    longitude: float | None
    existing_room_names: list[str]
    completed: bool


class SetupWizardService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], audit: AuditRecorder) -> None:
        self._uow_factory = uow_factory
        self._audit = audit

    async def set_location_and_timezone(
        self,
        actor: Actor,
        *,
        household_id: str,
        timezone: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> None:
        require_permission(actor, "users:manage")
        require_same_household(actor, household_id)

        rounded_latitude = round(latitude, _LOCATION_DECIMAL_PLACES) if latitude is not None else None
        rounded_longitude = round(longitude, _LOCATION_DECIMAL_PLACES) if longitude is not None else None

        with self._uow_factory() as uow:
            if uow.households.get_by_id(household_id) is None:
                raise HouseholdNotFoundError(household_id)
            uow.households.set_timezone_and_location(
                household_id, timezone=timezone, latitude=rounded_latitude, longitude=rounded_longitude
            )
            uow.commit()

        self._audit.record(
            actor=actor,
            action="setup_wizard.location_set",
            target_type="household",
            target_id=household_id,
            outcome="success",
            metadata={"timezone": timezone},
        )

    async def add_rooms(self, actor: Actor, *, household_id: str, room_names: list[str]) -> list[RoomRecord]:
        require_permission(actor, "rooms:manage")
        require_same_household(actor, household_id)

        with self._uow_factory() as uow:
            if uow.households.get_by_id(household_id) is None:
                raise HouseholdNotFoundError(household_id)

            existing_names_lower = {room.name.lower() for room in uow.rooms.list_by_household(household_id)}
            created = []
            for name in room_names:
                if name.lower() in existing_names_lower:
                    continue  # retry-safe: never create the same room twice
                room = uow.rooms.add(household_id=household_id, name=name)
                created.append(room)
                existing_names_lower.add(name.lower())
            uow.commit()

        self._audit.record(
            actor=actor,
            action="setup_wizard.rooms_added",
            target_type="household",
            target_id=household_id,
            outcome="success",
            metadata={"roomNames": [room.name for room in created]},
        )
        return created

    async def complete_setup(self, actor: Actor, *, household_id: str) -> None:
        require_permission(actor, "users:manage")
        require_same_household(actor, household_id)

        with self._uow_factory() as uow:
            if uow.households.get_by_id(household_id) is None:
                raise HouseholdNotFoundError(household_id)
            uow.households.mark_setup_completed(household_id)
            uow.commit()

        self._audit.record(
            actor=actor,
            action="setup_wizard.completed",
            target_type="household",
            target_id=household_id,
            outcome="success",
            metadata={},
        )

    async def get_progress(self, actor: Actor, *, household_id: str) -> WizardProgress:
        require_permission(actor, "users:manage")
        require_same_household(actor, household_id)

        with self._uow_factory() as uow:
            household = uow.households.get_by_id(household_id)
            if household is None:
                raise HouseholdNotFoundError(household_id)
            rooms = uow.rooms.list_by_household(household_id)

        return WizardProgress(
            timezone=household.timezone,
            latitude=household.latitude,
            longitude=household.longitude,
            existing_room_names=[room.name for room in rooms],
            completed=household.setup_completed_at is not None,
        )
