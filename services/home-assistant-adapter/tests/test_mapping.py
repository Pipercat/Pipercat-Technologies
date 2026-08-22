"""Pure unit tests for the HA-entity <-> SystemONE-device-dict mapping
(S1V2-02-016) - no network, no Home Assistant instance needed."""

import pytest

from home_assistant_adapter.errors import CapabilityNotSupportedError
from home_assistant_adapter.mapping import (
    command_to_service_call,
    derive_device_id,
    entity_domain,
    state_to_device_dict,
)


def test_device_id_is_never_the_raw_entity_id():
    """"HA-spezifische IDs nie als öffentliche SystemONE-Primärschlüssel
    verwenden" - the derived id must not equal or contain the entity_id."""
    device_id = derive_device_id("light.bed_light")
    assert device_id != "light.bed_light"
    assert "light.bed_light" not in device_id


def test_device_id_derivation_is_deterministic():
    assert derive_device_id("light.bed_light") == derive_device_id("light.bed_light")


def test_different_entities_derive_different_device_ids():
    assert derive_device_id("light.bed_light") != derive_device_id("light.kitchen_lights")


def test_entity_domain_extraction():
    assert entity_domain("light.bed_light") == "light"
    assert entity_domain("cover.garage_door") == "cover"


def test_state_to_device_dict_maps_a_light():
    state = {
        "entity_id": "light.bed_light",
        "state": "on",
        "attributes": {"friendly_name": "Bed Light", "brightness": 180},
    }
    device = state_to_device_dict(state)

    assert device["id"] == derive_device_id("light.bed_light")
    assert device["name"] == "Bed Light"
    assert device["device_type"] == "light"
    assert device["manufacturer_metadata"]["entityId"] == "light.bed_light"
    assert device["manufacturer_metadata"]["vendor"] == "home_assistant"
    assert device["capabilities"]["on_off"] == {"type": "on_off", "is_on": True}
    assert device["capabilities"]["brightness"]["percent"] == round(180 / 255 * 100)


def test_state_to_device_dict_maps_a_cover_position():
    state = {
        "entity_id": "cover.garage_door",
        "state": "open",
        "attributes": {"friendly_name": "Garage Door", "current_position": 42},
    }
    device = state_to_device_dict(state)
    assert device["capabilities"]["position"] == {"type": "position", "percent_open": 42}


def test_state_to_device_dict_maps_a_temperature_sensor():
    state = {
        "entity_id": "sensor.outside_temperature",
        "state": "21.5",
        "attributes": {"friendly_name": "Outside Temperature", "device_class": "temperature"},
    }
    device = state_to_device_dict(state)
    assert device["capabilities"]["temperature"] == {"type": "temperature", "celsius": 21.5}


def test_state_to_device_dict_handles_unknown_domains_without_crashing():
    """Discovery must be permissive - an entity type SystemONE doesn't
    understand yet is still listed, just with no capabilities."""
    state = {"entity_id": "automation.morning_routine", "state": "on", "attributes": {}}
    device = state_to_device_dict(state)
    assert device["device_type"] == "automation"
    assert device["capabilities"] == {}


# --- S1V2-02-018: locks, climate, camera, compatibility marking -----------


def test_state_to_device_dict_maps_a_lock():
    state = {"entity_id": "lock.front_door", "state": "locked", "attributes": {"friendly_name": "Front Door"}}
    device = state_to_device_dict(state)
    assert device["capabilities"]["lock"] == {"type": "lock", "is_locked": True}
    assert device["compatibility"] == "supported"


def test_lock_transitional_state_is_not_guessed():
    """"nicht erraten" - "jammed"/"locking"/"unlocking" are not silently
    mapped to either boolean."""
    for transitional_state in ("locking", "unlocking", "jammed"):
        state = {"entity_id": "lock.front_door", "state": transitional_state, "attributes": {}}
        device = state_to_device_dict(state)
        assert "lock" not in device["capabilities"]


def test_state_to_device_dict_maps_a_climate_entity():
    state = {
        "entity_id": "climate.living_room",
        "state": "heat",
        "attributes": {"friendly_name": "Living Room Thermostat", "hvac_mode": "heat", "temperature": 21.0},
    }
    device = state_to_device_dict(state)
    assert device["capabilities"]["climate"] == {"type": "climate", "target_celsius": 21.0, "mode": "heat"}
    assert device["compatibility"] == "supported"


def test_climate_unrecognized_hvac_mode_is_not_guessed():
    """"nicht erraten" - HA modes SystemONE doesn't normalize to
    (dry/fan_only/heat_cool) must not be mapped to the closest guess."""
    for unrecognized_mode in ("dry", "fan_only", "heat_cool"):
        state = {
            "entity_id": "climate.living_room",
            "state": unrecognized_mode,
            "attributes": {"hvac_mode": unrecognized_mode, "temperature": 21.0},
        }
        device = state_to_device_dict(state)
        assert "climate" not in device["capabilities"]


def test_state_to_device_dict_maps_a_camera():
    state = {"entity_id": "camera.front_porch", "state": "streaming", "attributes": {"friendly_name": "Front Porch"}}
    device = state_to_device_dict(state)
    assert device["capabilities"]["camera_stream"] == {"type": "camera_stream", "is_available": True}
    assert device["compatibility"] == "supported"
    # The capability only ever reports availability - never a stream URL,
    # token, or any other access detail (that's a separate, security-
    # sensitive future task, per app/domain/capabilities.py's docstring).
    assert set(device["capabilities"]["camera_stream"].keys()) == {"type", "is_available"}


def test_unavailable_camera_reports_no_stream_capability():
    state = {"entity_id": "camera.front_porch", "state": "unavailable", "attributes": {}}
    device = state_to_device_dict(state)
    assert "camera_stream" not in device["capabilities"]


@pytest.mark.parametrize(
    "entity_id,domain_word",
    [
        ("light.bed_light", "light"),
        ("switch.decorative", "switch"),
        ("cover.garage_door", "cover"),
        ("sensor.outside_temperature", "sensor"),
        ("lock.front_door", "lock"),
        ("climate.living_room", "climate"),
        ("camera.front_porch", "camera"),
    ],
)
def test_known_smart_home_domains_are_marked_supported(entity_id, domain_word):
    device = state_to_device_dict({"entity_id": entity_id, "state": "on", "attributes": {}})
    assert device["compatibility"] == "supported"


def test_binary_sensor_is_deliberately_marked_unsupported():
    """A binary_sensor's boolean state means different things per
    device_class (motion/door/presence/...) - mapping it to the
    commandable on_off capability would be exactly the kind of guessing
    this task forbids, so it stays unsupported until a dedicated
    boolean-sensor capability exists."""
    device = state_to_device_dict({"entity_id": "binary_sensor.front_door_open", "state": "on", "attributes": {}})
    assert device["compatibility"] == "unsupported"
    assert device["capabilities"] == {}


def test_unknown_domain_is_marked_unsupported():
    device = state_to_device_dict({"entity_id": "automation.morning_routine", "state": "on", "attributes": {}})
    assert device["compatibility"] == "unsupported"


def test_device_dict_never_leaks_ha_vocabulary_outside_manufacturer_metadata():
    """"UI/API sehen nur SystemONE-Capabilities" - every capability key
    and its `type` field must be a stable SystemONE CapabilityType value,
    never a raw HA domain/attribute name, anywhere except the deliberately
    opaque manufacturer_metadata bag."""
    fixtures = [
        {"entity_id": "light.bed_light", "state": "on", "attributes": {"brightness": 128}},
        {"entity_id": "lock.front_door", "state": "locked", "attributes": {}},
        {
            "entity_id": "climate.living_room",
            "state": "cool",
            "attributes": {"hvac_mode": "cool", "temperature": 19.5},
        },
        {"entity_id": "camera.front_porch", "state": "idle", "attributes": {}},
    ]
    known_capability_types = {"on_off", "brightness", "position", "temperature", "lock", "climate", "camera_stream"}

    for state in fixtures:
        device = state_to_device_dict(state)
        for key, value in device["capabilities"].items():
            assert key in known_capability_types
            assert value["type"] in known_capability_types


def test_state_to_device_dict_handles_unavailable_sensor_gracefully():
    state = {
        "entity_id": "sensor.outside_temperature",
        "state": "unavailable",
        "attributes": {"device_class": "temperature"},
    }
    device = state_to_device_dict(state)
    assert "temperature" not in device["capabilities"]


def test_command_to_service_call_on_off_for_light():
    domain, service, extra = command_to_service_call("light", {"type": "on_off", "is_on": True})
    assert (domain, service, extra) == ("light", "turn_on", {})

    domain, service, extra = command_to_service_call("light", {"type": "on_off", "is_on": False})
    assert (domain, service, extra) == ("light", "turn_off", {})


def test_command_to_service_call_brightness_converts_percent_to_ha_scale():
    domain, service, extra = command_to_service_call("light", {"type": "brightness", "percent": 50})
    assert (domain, service) == ("light", "turn_on")
    assert extra == {"brightness": round(50 / 100 * 255)}


def test_command_to_service_call_position_for_cover():
    domain, service, extra = command_to_service_call("cover", {"type": "position", "percent_open": 75})
    assert (domain, service, extra) == ("cover", "set_cover_position", {"position": 75})


def test_command_to_service_call_rejects_unsupported_combination():
    with pytest.raises(CapabilityNotSupportedError):
        command_to_service_call("sensor", {"type": "on_off", "is_on": True})


def test_command_to_service_call_lock_and_unlock():
    domain, service, extra = command_to_service_call("lock", {"type": "lock", "is_locked": True})
    assert (domain, service, extra) == ("lock", "lock", {})

    domain, service, extra = command_to_service_call("lock", {"type": "lock", "is_locked": False})
    assert (domain, service, extra) == ("lock", "unlock", {})


def test_command_to_service_call_climate_sets_temperature_and_mode():
    domain, service, extra = command_to_service_call(
        "climate", {"type": "climate", "target_celsius": 22.5, "mode": "heat"}
    )
    assert (domain, service) == ("climate", "set_temperature")
    assert extra == {"temperature": 22.5, "hvac_mode": "heat"}


def test_command_to_service_call_rejects_camera_stream_commands():
    """camera_stream is read-only - there is no HA service call for it."""
    with pytest.raises(CapabilityNotSupportedError):
        command_to_service_call("camera", {"type": "camera_stream", "is_available": True})
