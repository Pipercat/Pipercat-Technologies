"""S1V2-02-017 Definition of Done: "Mehrfacher Import ist idempotent;
Umbenennung/Room-Wechsel/temporär offline verursachen keine neuen
Geräteobjekte"."""

import pytest

from app.audit import InMemoryAuditRecorder
from app.authorization import AuthorizationError, CrossHouseholdAccessError
from app.services.ha_import import HomeAssistantImportService
from tests.fakes import FakeUnitOfWork, make_actor

HOUSEHOLD = "hh-1"
INTEGRATION = "integration-1"


class FakeHomeAssistantAdapter:
    def __init__(self) -> None:
        self.areas: list[dict] = []
        self.devices: list[dict] = []
        self.entity_registry: list[dict] = []
        self.device_registry: list[dict] = []

    async def list_areas(self) -> list[dict]:
        return self.areas

    async def list_devices(self) -> list[dict]:
        return self.devices

    async def list_entity_registry(self) -> list[dict]:
        return self.entity_registry

    async def list_device_registry(self) -> list[dict]:
        return self.device_registry


def _device_dict(entity_id: str, name: str, device_type: str = "light") -> dict:
    return {
        "id": f"derived-{entity_id}",
        "name": name,
        "device_type": device_type,
        "manufacturer_metadata": {"vendor": "home_assistant", "entityId": entity_id},
        "capabilities": {},
    }


@pytest.fixture
def rig():
    uow = FakeUnitOfWork()
    audit = InMemoryAuditRecorder()
    service = HomeAssistantImportService(uow_factory=lambda: uow, audit=audit)
    adapter = FakeHomeAssistantAdapter()
    admin = make_actor("devices:manage", household_id=HOUSEHOLD)
    return service, uow, audit, adapter, admin


# --- Areas -> Rooms ----------------------------------------------------


async def test_import_areas_creates_new_rooms(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.areas = [{"id": "living_room", "name": "Living Room"}]

    summary = await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.created == 1
    rooms = uow.rooms.list_by_household(HOUSEHOLD)
    assert [r.name for r in rooms] == ["Living Room"]
    assert rooms[0].external_id == "living_room"


async def test_repeated_area_import_is_idempotent_no_duplicate_rooms(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.areas = [{"id": "living_room", "name": "Living Room"}]

    await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    summary = await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.created == 0
    assert summary.unchanged == 1
    assert len(uow.rooms.list_by_household(HOUSEHOLD)) == 1


async def test_area_rename_updates_the_same_room_not_a_new_one(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.areas = [{"id": "living_room", "name": "Living Room"}]
    await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    original_id = uow.rooms.list_by_household(HOUSEHOLD)[0].id

    adapter.areas = [{"id": "living_room", "name": "Lounge"}]
    summary = await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.updated == 1
    rooms = uow.rooms.list_by_household(HOUSEHOLD)
    assert len(rooms) == 1
    assert rooms[0].id == original_id
    assert rooms[0].name == "Lounge"


# --- Entities -> Devices -------------------------------------------------


async def test_import_devices_creates_new_devices(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]

    summary = await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.created == 1
    devices = uow.devices.list_by_household(HOUSEHOLD)
    assert [d.name for d in devices] == ["Bed Light"]
    assert devices[0].external_id == "light.bed_light"


async def test_repeated_device_import_is_idempotent_no_duplicate_devices(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]

    await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    summary = await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.created == 0
    assert summary.unchanged == 1
    assert len(uow.devices.list_by_household(HOUSEHOLD)) == 1


async def test_device_rename_updates_the_same_device_not_a_new_one(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]
    await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    original_id = uow.devices.list_by_household(HOUSEHOLD)[0].id

    adapter.devices = [_device_dict("light.bed_light", "Master Bedroom Light")]
    summary = await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.updated == 1
    devices = uow.devices.list_by_household(HOUSEHOLD)
    assert len(devices) == 1
    assert devices[0].id == original_id
    assert devices[0].name == "Master Bedroom Light"


async def test_device_temporarily_missing_from_a_report_is_left_untouched(rig):
    """"temporär offline verursachen keine neuen Geräteobjekte" - and no
    deletion either. A device absent from one import (e.g. HA restarting)
    must survive unchanged until it's seen again."""
    service, uow, _audit, adapter, admin = rig
    adapter.devices = [_device_dict("light.bed_light", "Bed Light"), _device_dict("switch.decorative", "Deco Switch")]
    await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]  # switch.decorative temporarily absent
    summary = await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.created == 0  # nothing new
    devices = uow.devices.list_by_household(HOUSEHOLD)
    assert len(devices) == 2  # the absent device was neither deleted nor duplicated
    assert {d.name for d in devices} == {"Bed Light", "Deco Switch"}


# --- Room assignment via entity/device registry --------------------------


async def test_device_room_resolved_from_its_own_entity_registry_area(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.areas = [{"id": "living_room", "name": "Living Room"}]
    await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    room_id = uow.rooms.list_by_household(HOUSEHOLD)[0].id

    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]
    adapter.entity_registry = [{"entityId": "light.bed_light", "areaId": "living_room", "deviceId": None}]

    await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    device = uow.devices.list_by_household(HOUSEHOLD)[0]
    assert device.room_id == room_id


async def test_device_room_falls_back_to_its_parent_ha_devices_area(rig):
    """Standard HA behaviour: most integrations set the area on the
    device registry entry, not on each individual entity."""
    service, uow, _audit, adapter, admin = rig
    adapter.areas = [{"id": "living_room", "name": "Living Room"}]
    await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    room_id = uow.rooms.list_by_household(HOUSEHOLD)[0].id

    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]
    adapter.entity_registry = [{"entityId": "light.bed_light", "areaId": None, "deviceId": "ha-device-1"}]
    adapter.device_registry = [{"id": "ha-device-1", "areaId": "living_room"}]

    await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    device = uow.devices.list_by_household(HOUSEHOLD)[0]
    assert device.room_id == room_id


async def test_device_room_change_updates_the_same_device(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.areas = [{"id": "living_room", "name": "Living Room"}, {"id": "bedroom", "name": "Bedroom"}]
    await service.import_areas(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    rooms = {r.external_id: r.id for r in uow.rooms.list_by_household(HOUSEHOLD)}

    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]
    adapter.entity_registry = [{"entityId": "light.bed_light", "areaId": "living_room", "deviceId": None}]
    await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
    original_id = uow.devices.list_by_household(HOUSEHOLD)[0].id
    assert uow.devices.list_by_household(HOUSEHOLD)[0].room_id == rooms["living_room"]

    adapter.entity_registry = [{"entityId": "light.bed_light", "areaId": "bedroom", "deviceId": None}]
    summary = await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert summary.updated == 1
    devices = uow.devices.list_by_household(HOUSEHOLD)
    assert len(devices) == 1
    assert devices[0].id == original_id
    assert devices[0].room_id == rooms["bedroom"]


async def test_device_with_unimported_area_has_no_room_not_an_error(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]
    adapter.entity_registry = [{"entityId": "light.bed_light", "areaId": "unknown_area", "deviceId": None}]

    await service.import_devices(admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)

    assert uow.devices.list_by_household(HOUSEHOLD)[0].room_id is None


# --- sync_household ordering -----------------------------------------------


async def test_sync_household_imports_areas_before_devices(rig):
    service, uow, _audit, adapter, admin = rig
    adapter.areas = [{"id": "living_room", "name": "Living Room"}]
    adapter.devices = [_device_dict("light.bed_light", "Bed Light")]
    adapter.entity_registry = [{"entityId": "light.bed_light", "areaId": "living_room", "deviceId": None}]

    areas_summary, devices_summary = await service.sync_household(
        admin, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter
    )

    assert areas_summary.created == 1
    assert devices_summary.created == 1
    room_id = uow.rooms.list_by_household(HOUSEHOLD)[0].id
    assert uow.devices.list_by_household(HOUSEHOLD)[0].room_id == room_id


# --- authorization -----------------------------------------------------


async def test_import_areas_without_permission_is_denied(rig):
    service, _uow, _audit, adapter, _admin = rig
    unauthorized = make_actor(household_id=HOUSEHOLD)
    with pytest.raises(AuthorizationError):
        await service.import_areas(unauthorized, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)


async def test_import_devices_for_a_different_household_is_rejected(rig):
    service, _uow, _audit, adapter, _admin = rig
    attacker = make_actor("devices:manage", household_id="some-other-household")
    with pytest.raises(CrossHouseholdAccessError):
        await service.import_devices(attacker, household_id=HOUSEHOLD, integration_id=INTEGRATION, adapter=adapter)
