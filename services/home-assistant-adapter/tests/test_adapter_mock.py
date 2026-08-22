"""Mocked HomeAssistantAdapter tests (S1V2-02-016 DoD: "Mock- ... Integrationstest").

Exercises HomeAssistantAdapter's own logic (id derivation, entity_id
lookup, command mapping) with HomeAssistantClient replaced by a
hand-written fake matching its public surface - no real network, no
Home Assistant instance. See test_real_ha_integration.py for the
complementary real-instance test the DoD also requires.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from home_assistant_adapter.adapter import HomeAssistantAdapter
from home_assistant_adapter.errors import DeviceNotFoundError
from home_assistant_adapter.mapping import derive_device_id


class FakeHomeAssistantClient:
    def __init__(self, states: list[dict[str, Any]]) -> None:
        self.states = states
        self.service_calls: list[tuple[str, str, dict]] = []
        self._events: list[dict] = []
        self.zha_devices: list[dict] = []
        self.sent_commands: list[tuple[str, dict]] = []
        self.matter_node_diagnostics_result: dict = {}

    async def get_states(self) -> list[dict[str, Any]]:
        return self.states

    async def call_service(self, domain: str, service: str, service_data: dict) -> list[dict]:
        self.service_calls.append((domain, service, service_data))
        for state in self.states:
            if state["entity_id"] == service_data.get("entity_id"):
                if service == "turn_on":
                    state["state"] = "on"
                    if "brightness" in service_data:
                        state.setdefault("attributes", {})["brightness"] = service_data["brightness"]
                elif service == "turn_off":
                    state["state"] = "off"
        return []

    async def send_command(self, command_type: str, **extra) -> Any:
        self.sent_commands.append((command_type, extra))
        if command_type == "config/area_registry/list":
            return [{"area_id": "living_room", "name": "Living Room"}]
        if command_type == "config/entity_registry/list":
            return [{"entity_id": "light.bed_light", "area_id": None, "device_id": "device-1"}]
        if command_type == "config/device_registry/list":
            return [{"id": "device-1", "area_id": "living_room"}]
        if command_type == "zha/devices":
            return self.zha_devices
        if command_type in ("matter/commission", "matter/commission_on_network", "matter/remove_matter_fabric"):
            return None
        if command_type == "matter/node_diagnostics":
            return self.matter_node_diagnostics_result
        raise AssertionError(f"unexpected command {command_type}")

    def queue_event(self, event: dict) -> None:
        self._events.append(event)

    async def subscribe_events(self, event_type: str = "state_changed") -> AsyncIterator[dict]:
        yield {"kind": "connected"}
        for event in self._events:
            yield {"kind": "event", "event": event}

    async def aclose(self) -> None:
        pass


def _adapter_with_fake_client(states: list[dict[str, Any]]) -> tuple[HomeAssistantAdapter, FakeHomeAssistantClient]:
    adapter = HomeAssistantAdapter(base_url="http://unused.invalid", access_token="unused")
    fake = FakeHomeAssistantClient(states)
    adapter._client = fake  # replacing the real client is the whole point of this test
    return adapter, fake


def _bed_light_state() -> dict[str, Any]:
    return {
        "entity_id": "light.bed_light",
        "state": "off",
        "attributes": {"friendly_name": "Bed Light"},
    }


async def test_list_devices_maps_ha_states_to_device_dicts():
    adapter, _fake = _adapter_with_fake_client([_bed_light_state()])

    devices = await adapter.list_devices()

    assert len(devices) == 1
    assert devices[0]["id"] == derive_device_id("light.bed_light")
    assert devices[0]["name"] == "Bed Light"
    assert devices[0]["manufacturer_metadata"]["entityId"] == "light.bed_light"


async def test_apply_command_calls_the_correct_ha_service():
    adapter, fake = _adapter_with_fake_client([_bed_light_state()])
    devices = await adapter.list_devices()
    device_id = devices[0]["id"]

    new_state = await adapter.apply_command(device_id, {"type": "on_off", "is_on": True})

    assert fake.service_calls == [("light", "turn_on", {"entity_id": "light.bed_light"})]
    assert new_state == {"type": "on_off", "is_on": True}


async def test_apply_command_on_an_unknown_device_id_raises():
    adapter, _fake = _adapter_with_fake_client([_bed_light_state()])
    await adapter.list_devices()

    with pytest.raises(DeviceNotFoundError):
        await adapter.apply_command("never-listed-device-id", {"type": "on_off", "is_on": True})


async def test_apply_command_before_any_discovery_raises_device_not_found():
    """The entity_id lookup cache is only populated by list_devices() -
    commanding a device id before ever discovering it must fail clearly,
    not silently no-op."""
    adapter, _fake = _adapter_with_fake_client([_bed_light_state()])

    with pytest.raises(DeviceNotFoundError):
        await adapter.apply_command(derive_device_id("light.bed_light"), {"type": "on_off", "is_on": True})


async def test_list_areas_maps_ha_area_registry():
    adapter, _fake = _adapter_with_fake_client([])

    areas = await adapter.list_areas()

    assert areas == [{"id": "living_room", "name": "Living Room"}]


async def test_list_entity_registry_maps_ha_rows():
    adapter, _fake = _adapter_with_fake_client([])

    entities = await adapter.list_entity_registry()

    assert entities == [{"entityId": "light.bed_light", "areaId": None, "deviceId": "device-1"}]


async def test_list_device_registry_maps_ha_rows():
    adapter, _fake = _adapter_with_fake_client([])

    devices = await adapter.list_device_registry()

    assert devices == [{"id": "device-1", "areaId": "living_room"}]


async def test_subscribe_events_yields_a_resync_marker_before_any_device_update():
    """S1V2-02-020: every (re)subscription - including the very first -
    must surface a resync trigger before any incremental update, so a
    caller building an in-memory snapshot always gets "start fresh" before
    "here's one more delta"."""
    adapter, fake = _adapter_with_fake_client([])
    fake.queue_event(
        {
            "event_type": "state_changed",
            "data": {
                "entity_id": "light.bed_light",
                "new_state": {"entity_id": "light.bed_light", "state": "on", "attributes": {}},
            },
        }
    )

    events = [event async for event in adapter.subscribe_events()]

    assert events[0] == {"kind": "resync"}
    assert len(events) == 2
    assert events[1]["kind"] == "device_changed"
    assert events[1]["entityId"] == "light.bed_light"
    assert events[1]["deviceId"] == derive_device_id("light.bed_light")


async def test_subscribe_events_populates_the_entity_lookup_cache():
    """A device first seen through a live event (not list_devices()) must
    still be commandable afterwards."""
    adapter, fake = _adapter_with_fake_client(
        [{"entity_id": "switch.decorative_lights", "state": "off", "attributes": {}}]
    )
    fake.queue_event(
        {
            "event_type": "state_changed",
            "data": {
                "entity_id": "switch.decorative_lights",
                "new_state": {"entity_id": "switch.decorative_lights", "state": "off", "attributes": {}},
            },
        }
    )

    [event async for event in adapter.subscribe_events()]

    device_id = derive_device_id("switch.decorative_lights")
    new_state = await adapter.apply_command(device_id, {"type": "on_off", "is_on": True})
    assert new_state == {"type": "on_off", "is_on": True}
    assert fake.service_calls == [("switch", "turn_on", {"entity_id": "switch.decorative_lights"})]


# --- ZHA / Zigbee pairing (S1V2-02-022) -------------------------------------


async def test_zha_permit_join_calls_the_real_zha_permit_service():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.zha_permit_join(duration_seconds=120)

    assert fake.service_calls == [("zha", "permit", {"duration": 120})]


async def test_zha_permit_join_defaults_to_sixty_seconds():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.zha_permit_join()

    assert fake.service_calls == [("zha", "permit", {"duration": 60})]


async def test_zha_remove_device_calls_the_real_zha_remove_service():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.zha_remove_device(ieee="00:11:22:33:44:55:66:77")

    assert fake.service_calls == [("zha", "remove", {"ieee": "00:11:22:33:44:55:66:77"})]


async def test_zha_list_devices_passes_through_the_raw_zha_devices_command():
    adapter, fake = _adapter_with_fake_client([])
    fake.zha_devices = [{"ieee": "00:11:22:33:44:55:66:77", "entities": [{"entity_id": "light.bed_light"}]}]

    devices = await adapter.zha_list_devices()

    assert devices == fake.zha_devices


# --- Matter commissioning (S1V2-02-023) -------------------------------------


async def test_matter_commission_with_code_calls_the_real_matter_commission_command():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.matter_commission_with_code(code="MT:ABCDEF")

    assert fake.sent_commands == [("matter/commission", {"code": "MT:ABCDEF", "network_only": True})]


async def test_matter_commission_with_code_forwards_network_only_false():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.matter_commission_with_code(code="MT:ABCDEF", network_only=False)

    assert fake.sent_commands == [("matter/commission", {"code": "MT:ABCDEF", "network_only": False})]


async def test_matter_commission_on_network_calls_the_real_command():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.matter_commission_on_network(pin=12345678)

    assert fake.sent_commands == [("matter/commission_on_network", {"pin": 12345678})]


async def test_matter_commission_on_network_forwards_ip_addr_when_given():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.matter_commission_on_network(pin=12345678, ip_addr="192.168.1.42")

    assert fake.sent_commands == [("matter/commission_on_network", {"pin": 12345678, "ip_addr": "192.168.1.42"})]


async def test_matter_remove_fabric_calls_the_real_command():
    adapter, fake = _adapter_with_fake_client([])

    await adapter.matter_remove_fabric(ha_device_id="ha-device-1", fabric_index=1)

    assert fake.sent_commands == [("matter/remove_matter_fabric", {"device_id": "ha-device-1", "fabric_index": 1})]


async def test_matter_node_diagnostics_passes_through_raw_data():
    adapter, fake = _adapter_with_fake_client([])
    fake.matter_node_diagnostics_result = {"fabrics": [{"fabric_index": 1}]}

    result = await adapter.matter_node_diagnostics(ha_device_id="ha-device-1")

    assert result == {"fabrics": [{"fabric_index": 1}]}
    assert fake.sent_commands == [("matter/node_diagnostics", {"device_id": "ha-device-1"})]


async def test_resolve_ha_device_id_finds_the_device_via_entity_registry():
    adapter, _fake = _adapter_with_fake_client([_bed_light_state()])
    device_id = (await adapter.list_devices())[0]["id"]

    ha_device_id = await adapter.resolve_ha_device_id(device_id)

    assert ha_device_id == "device-1"  # from FakeHomeAssistantClient's config/entity_registry/list


async def test_resolve_ha_device_id_returns_none_for_an_undiscovered_device():
    adapter, _fake = _adapter_with_fake_client([_bed_light_state()])

    ha_device_id = await adapter.resolve_ha_device_id("never-listed-device")

    assert ha_device_id is None
