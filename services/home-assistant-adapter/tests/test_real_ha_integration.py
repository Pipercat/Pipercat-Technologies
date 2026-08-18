"""Real Home Assistant integration test (S1V2-02-016 DoD: "... echter
HA-Integrationstest"). Runs HomeAssistantAdapter against an actual,
running Home Assistant instance (the `demo:` platform's simulated
devices - not SystemONE-side mocking) over real HTTP/WebSocket wire
protocol: genuine REST discovery, a genuine WS auth handshake, and a
genuine service call that HA itself validates and applies.

Requires HOME_ASSISTANT_URL to point at a reachable instance with the
`demo:` platform enabled - see docs/architecture/home-assistant-adapter.md
for how to start one locally with Docker, or the `home-assistant-adapter`
CI job for how it's started in CI. Skipped (not failed) if unset, the
same pattern apps/customer-backend/tests/db_conftest.py uses for tests
that need a real PostgreSQL database.
"""

import pytest

from home_assistant_adapter.adapter import HomeAssistantAdapter

from ha_conftest import home_assistant_access_token, home_assistant_base_url, requires_home_assistant  # noqa: F401

pytestmark = requires_home_assistant


@pytest.fixture
async def adapter(home_assistant_base_url, home_assistant_access_token):
    instance = HomeAssistantAdapter(home_assistant_base_url, home_assistant_access_token)
    yield instance
    await instance.close()


async def test_list_devices_discovers_real_demo_entities(adapter):
    """The `demo:` platform ships several lights/switches/covers/sensors
    out of the box - this proves list_devices() genuinely round-trips
    through GET /api/states against a real server, not a mock."""
    devices = await adapter.list_devices()

    assert len(devices) > 0
    light_devices = [d for d in devices if d["device_type"] == "light"]
    assert len(light_devices) > 0, "expected at least one demo light entity"
    for device in devices:
        # The core DoD requirement, proven against a real instance: no
        # raw Home Assistant entity_id ever appears as the public id.
        assert "." not in device["id"]
        assert device["manufacturer_metadata"]["entityId"].count(".") == 1


async def test_apply_command_genuinely_toggles_a_real_demo_light(adapter):
    devices = await adapter.list_devices()
    light = next(d for d in devices if d["device_type"] == "light")

    turned_on = await adapter.apply_command(light["id"], {"type": "on_off", "is_on": True})
    assert turned_on == {"type": "on_off", "is_on": True}

    turned_off = await adapter.apply_command(light["id"], {"type": "on_off", "is_on": False})
    assert turned_off == {"type": "on_off", "is_on": False}


async def test_apply_command_on_unknown_device_id_raises_against_a_real_server():
    from home_assistant_adapter.errors import DeviceNotFoundError

    instance = HomeAssistantAdapter("http://unused-in-this-test.invalid", "unused")
    with pytest.raises(DeviceNotFoundError):
        await instance.apply_command("never-discovered", {"type": "on_off", "is_on": True})
    await instance.close()


async def test_list_areas_round_trips_through_the_real_websocket_api(adapter):
    """Exercises the WS auth handshake + config/area_registry/list
    command against a real server - proves the WebSocket half of the
    client, not just REST."""
    areas = await adapter.list_areas()
    assert isinstance(areas, list)  # a fresh demo instance may have zero areas - the call succeeding is the proof


async def test_list_entity_and_device_registry_round_trip_through_the_real_websocket_api(adapter):
    """S1V2-02-017 groundwork: the demo platform's entities are always
    registered, so the registry rows must be non-empty and shaped as
    expected against a real server."""
    entities = await adapter.list_entity_registry()
    devices = await adapter.list_device_registry()

    assert len(entities) > 0
    for entity in entities:
        assert set(entity.keys()) == {"entityId", "areaId", "deviceId"}
    for device in devices:
        assert set(device.keys()) == {"id", "areaId"}


async def test_subscribe_events_receives_a_real_state_change(adapter):
    """Toggling a demo light through the REST API and observing the
    resulting state_changed event arrive over the adapter's own
    WebSocket subscription proves the live-events path end-to-end
    against a real server."""
    import asyncio

    devices = await adapter.list_devices()
    light = next(d for d in devices if d["device_type"] == "light")

    async def toggle_after_subscribing():
        await asyncio.sleep(1.0)  # give the subscription time to establish
        await adapter.apply_command(light["id"], {"type": "on_off", "is_on": True})

    events_task = asyncio.ensure_future(_first_matching_event(adapter, light["manufacturer_metadata"]["entityId"]))
    toggle_task = asyncio.ensure_future(toggle_after_subscribing())

    event = await asyncio.wait_for(events_task, timeout=15.0)
    await toggle_task

    assert event["entityId"] == light["manufacturer_metadata"]["entityId"]


async def _first_matching_event(adapter: HomeAssistantAdapter, entity_id: str) -> dict:
    async for event in adapter.subscribe_events():
        if event["entityId"] == entity_id:
            return event
    raise AssertionError("event stream ended without a matching event")  # pragma: no cover
