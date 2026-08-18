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
