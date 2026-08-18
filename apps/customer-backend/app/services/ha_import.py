"""Import Home Assistant areas/devices into SystemONE's Room/Device
registry with a stable, idempotent mapping (S1V2-02-017).

DEC-6/DEC-7: re-running the import must never create duplicate Rooms or
Devices - each HA area/entity is matched by its external_id against
what's already stored (Room.external_id/Device.external_id), so a
second import of the same household finds and updates the same rows
instead of inserting new ones. A rename or area/room change updates the
existing row in place; an entity that is temporarily missing from the
current HA report (offline, HA still starting up, a transient API
hiccup) is simply left untouched - this service never deletes a Room or
Device on a missing report, only ever adds or updates one it currently
sees. Actual removal of a device/room confirmed gone from HA is a
deliberate non-goal here ("kontrolliert behandeln" - controlled, not
automatic-silent deletion); it would need its own explicit task.

`HomeAssistantImportPort` is a local, minimal Protocol (not an import of
`home_assistant_adapter.HomeAssistantAdapter`) so this service can be
unit-tested against a fake without services/home-assistant-adapter's
network dependencies (httpx/websockets) needing to be installed here -
apps/customer-backend is allowed to import services/home-assistant-adapter
directly (see docs/architecture/repo-structure.md's import table), but
doing so is unnecessary for this file to work correctly.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.audit import AuditRecorder
from app.authorization import Actor, require_permission, require_same_household
from app.uow import UnitOfWork


class HomeAssistantImportPort(Protocol):
    async def list_areas(self) -> list[dict[str, Any]]: ...

    async def list_devices(self) -> list[dict[str, Any]]: ...

    async def list_entity_registry(self) -> list[dict[str, Any]]: ...

    async def list_device_registry(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ImportSummary:
    created: int
    updated: int
    unchanged: int


class HomeAssistantImportService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], audit: AuditRecorder) -> None:
        self._uow_factory = uow_factory
        self._audit = audit

    async def import_areas(
        self, actor: Actor, *, household_id: str, integration_id: str, adapter: HomeAssistantImportPort
    ) -> ImportSummary:
        require_permission(actor, "devices:manage")
        require_same_household(actor, household_id)

        areas = await adapter.list_areas()
        created = updated = unchanged = 0

        with self._uow_factory() as uow:
            for area in areas:
                existing = uow.rooms.get_by_external_id(integration_id, area["id"])
                if existing is None:
                    uow.rooms.add(
                        household_id=household_id, name=area["name"], integration_id=integration_id, external_id=area["id"]
                    )
                    created += 1
                elif existing.name != area["name"]:
                    uow.rooms.update_name(existing.id, area["name"])
                    updated += 1
                else:
                    unchanged += 1
            uow.commit()

        self._audit.record(
            actor=actor,
            action="ha_import.areas_imported",
            target_type="household",
            target_id=household_id,
            outcome="success",
            metadata={"integrationId": integration_id, "created": created, "updated": updated, "unchanged": unchanged},
        )
        return ImportSummary(created=created, updated=updated, unchanged=unchanged)

    async def import_devices(
        self, actor: Actor, *, household_id: str, integration_id: str, adapter: HomeAssistantImportPort
    ) -> ImportSummary:
        """Must run after import_areas() for the same integration if
        up-to-date room assignment is wanted - a device whose area's Room
        hasn't been imported yet simply lands with no room (room_id=None),
        never an error."""
        require_permission(actor, "devices:manage")
        require_same_household(actor, household_id)

        devices = await adapter.list_devices()
        entity_area_id = await _resolve_entity_area_ids(adapter)
        created = updated = unchanged = 0

        with self._uow_factory() as uow:
            for device_dict in devices:
                entity_id = device_dict["manufacturer_metadata"]["entityId"]
                area_id = entity_area_id.get(entity_id)
                room = uow.rooms.get_by_external_id(integration_id, area_id) if area_id else None
                room_id = room.id if room else None

                existing = uow.devices.get_by_external_id(integration_id, entity_id)
                if existing is None:
                    uow.devices.add(
                        household_id=household_id,
                        integration_id=integration_id,
                        external_id=entity_id,
                        name=device_dict["name"],
                        device_type=device_dict["device_type"],
                        room_id=room_id,
                    )
                    created += 1
                elif existing.name != device_dict["name"] or existing.room_id != room_id:
                    uow.devices.update(existing.id, name=device_dict["name"], room_id=room_id)
                    updated += 1
                else:
                    unchanged += 1
            uow.commit()

        self._audit.record(
            actor=actor,
            action="ha_import.devices_imported",
            target_type="household",
            target_id=household_id,
            outcome="success",
            metadata={"integrationId": integration_id, "created": created, "updated": updated, "unchanged": unchanged},
        )
        return ImportSummary(created=created, updated=updated, unchanged=unchanged)

    async def sync_household(
        self, actor: Actor, *, household_id: str, integration_id: str, adapter: HomeAssistantImportPort
    ) -> tuple[ImportSummary, ImportSummary]:
        """Convenience: areas first, then devices, so device room lookups
        see the just-imported rooms."""
        areas_summary = await self.import_areas(
            actor, household_id=household_id, integration_id=integration_id, adapter=adapter
        )
        devices_summary = await self.import_devices(
            actor, household_id=household_id, integration_id=integration_id, adapter=adapter
        )
        return areas_summary, devices_summary


async def _resolve_entity_area_ids(adapter: HomeAssistantImportPort) -> dict[str, str | None]:
    """An entity's effective area is its own area_id if set, else its
    parent HA device's area_id (standard Home Assistant behaviour - most
    integrations set the area on the device, not each entity)."""
    entity_rows = await adapter.list_entity_registry()
    device_rows = await adapter.list_device_registry()
    area_by_device_id = {row["id"]: row.get("areaId") for row in device_rows}

    return {
        row["entityId"]: row.get("areaId") or area_by_device_id.get(row.get("deviceId"))
        for row in entity_rows
    }
