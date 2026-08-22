"""Repository interfaces (S1V2-02-003). Structural Protocols, same
rationale as app/domain/adapter_port.py: services depend on these shapes,
never on SQLAlchemy directly, so unit tests can substitute in-memory fakes
(see tests/fakes.py) without a database."""

from typing import Protocol

from .records import DeviceRecord, HouseholdRecord, RoomRecord, UserRecord


class HouseholdRepository(Protocol):
    def add(self, *, name: str, product_class: str) -> HouseholdRecord: ...

    def get_by_id(self, household_id: str) -> HouseholdRecord | None: ...

    def set_timezone_and_location(
        self, household_id: str, *, timezone: str, latitude: float | None, longitude: float | None
    ) -> None: ...

    def mark_setup_completed(self, household_id: str) -> None:
        """Idempotent - calling this again on an already-completed
        household is a no-op, never an error (S1V2-02-030: a resumed
        wizard may re-submit its final step)."""
        ...


class RoomRepository(Protocol):
    def add(
        self, *, household_id: str, name: str, integration_id: str | None = None, external_id: str | None = None
    ) -> RoomRecord: ...

    def get_by_external_id(self, integration_id: str, external_id: str) -> RoomRecord | None: ...

    def update_name(self, room_id: str, name: str) -> None:
        """Renaming an imported room (S1V2-02-017: HA area renamed) never
        creates a new Room - the same external_id keeps mapping to the
        same room_id, only its name changes."""
        ...

    def list_by_household(self, household_id: str) -> list[RoomRecord]: ...


class DeviceRepository(Protocol):
    def add(
        self,
        *,
        household_id: str,
        integration_id: str,
        external_id: str,
        name: str,
        device_type: str,
        room_id: str | None = None,
    ) -> DeviceRecord: ...

    def get_by_external_id(self, integration_id: str, external_id: str) -> DeviceRecord | None: ...

    def update(self, device_id: str, *, name: str, room_id: str | None) -> None:
        """Renaming or moving an already-registered device (S1V2-02-017)
        updates the existing row in place - never creates a new device
        object, matching the DoD "Umbenennung/Room-Wechsel... verursachen
        keine neuen Geräteobjekte"."""
        ...

    def list_by_household(self, household_id: str) -> list[DeviceRecord]: ...


class UserRepository(Protocol):
    def add(
        self,
        *,
        household_id: str,
        role_id: str,
        display_name: str,
        password_hash: str | None = None,
        pin_hash: str | None = None,
    ) -> UserRecord: ...

    def get_by_id(self, user_id: str) -> UserRecord | None: ...

    def get_permissions_for_role(self, role_id: str) -> frozenset[str]: ...

    def set_role(self, user_id: str, role_id: str) -> None: ...

    def set_pin_hash(self, user_id: str, pin_hash: str | None) -> None: ...


class RoleRepository(Protocol):
    def get_id_by_key(self, role_key: str) -> str | None: ...
