"""Translation between Home Assistant's entity/state model and
SystemONE's own device-shaped dicts (S1V2-02-016, extended in
S1V2-02-018 for locks/climate/camera + explicit compatibility marking).

"HA-spezifische IDs nie als öffentliche SystemONE-Primärschlüssel
verwenden": every device dict's `id` is derived from the HA entity_id via
a deterministic UUID5 hash, never the raw entity_id itself. The real
entity_id is kept only inside `manufacturer_metadata` (opaque,
vendor-specific detail - see apps/customer-backend/app/domain/device.py's
docstring for the same rule on the domain side).

"Unbekannte/inkompatible Entities nicht erraten, sondern als nicht
unterstützt/Beta markieren" (S1V2-02-018): every device dict carries a
`compatibility` field - `"supported"` if the entity's HA domain is one
this module knows how to interpret at all, `"unsupported"` otherwise.
Within a supported domain, an attribute value this module doesn't
recognize (an HA `hvac_mode` outside {off,heat,cool,auto}, a lock state
mid-transition like "jammed") is simply omitted from `capabilities`
rather than mapped to the nearest guess - a client sees "no reading yet"
never a wrong one. The full three-tier Certified/Compatible/Beta model
is a separate, later task (`S1V2-02-026`); this is only the binary
supported/unsupported signal that task's DoD needs.

Returns plain dicts, not `app.domain.device.DomainDevice`/
`app.domain.capabilities.CapabilityState` instances: this package has no
internal dependencies and cannot import those Pydantic models (see
errors.py's docstring for the same boundary constraint). The dicts are
shaped to match those models' fields field-for-field, so whichever future
task wires this adapter into `apps/customer-backend` can construct the
real Pydantic models from them (`DomainDevice(**d)`) or let FastAPI's
response_model validation coerce them directly - this is a deliberate,
duck-typed satisfaction of DeviceAdapterPort's structural contract, the
same choice already visible in the pre-existing adapter skeleton
(`import_devices() -> list[dict[str, Any]]`).

A persistent, stable device-registry mapping (surviving entity_id
renames, not just re-derivable from the current entity_id) is
S1V2-02-017's job, not this one - see "Bewusst nicht Teil dieser
Aufgabe" in docs/architecture/home-assistant-adapter.md.
"""

import uuid

# Fixed namespace so the same entity_id always derives the same device id
# across adapter restarts, without persisting anything ourselves yet.
_DEVICE_ID_NAMESPACE = uuid.UUID("6a6e2b7a-2f27-4a0a-9b7b-9a2b6c9a7b6a")

_DOMAIN_TO_DEVICE_TYPE = {
    "light": "light",
    "switch": "switch",
    "cover": "cover",
    "sensor": "sensor",
    "climate": "climate",
    "lock": "lock",
    "camera": "camera",
    "binary_sensor": "binary_sensor",
}

# Domains this module actually knows how to turn into capabilities.
# "binary_sensor" is deliberately excluded: its boolean state means
# different things per device_class (motion/door/presence/...) and none
# of them are the same thing as a commandable ON_OFF - mapping it to
# on_off would be exactly the "erraten" (guessing) this task forbids, so
# until a dedicated boolean-sensor capability exists it stays unsupported.
_SUPPORTED_DOMAINS = {"light", "switch", "cover", "sensor", "climate", "lock", "camera"}

_HA_HVAC_MODE_TO_CLIMATE_MODE = {"off": "off", "heat": "heat", "cool": "cool", "auto": "auto"}


def derive_device_id(entity_id: str) -> str:
    return str(uuid.uuid5(_DEVICE_ID_NAMESPACE, entity_id))


def entity_domain(entity_id: str) -> str:
    return entity_id.split(".", 1)[0]


def state_to_device_dict(state: dict) -> dict:
    """`state` is one element of GET /api/states's response body:
    {"entity_id": ..., "state": ..., "attributes": {...}}."""
    entity_id = state["entity_id"]
    domain = entity_domain(entity_id)
    attributes = state.get("attributes", {})

    return {
        "id": derive_device_id(entity_id),
        "name": attributes.get("friendly_name", entity_id),
        "room_id": None,  # area/room mapping is S1V2-02-017's job
        "device_type": _DOMAIN_TO_DEVICE_TYPE.get(domain, domain),
        "compatibility": "supported" if domain in _SUPPORTED_DOMAINS else "unsupported",
        "manufacturer_metadata": {"vendor": "home_assistant", "entityId": entity_id, "haDomain": domain},
        "capabilities": _capabilities_for(domain, state.get("state"), attributes),
    }


def _capabilities_for(domain: str, ha_state: str | None, attributes: dict) -> dict:
    capabilities: dict = {}

    if domain in ("light", "switch"):
        if ha_state in ("on", "off"):
            capabilities["on_off"] = {"type": "on_off", "is_on": ha_state == "on"}

    if domain == "light" and attributes.get("brightness") is not None:
        # HA brightness is 0-255; SystemONE's BrightnessState is a 0-100 percent.
        percent = round(attributes["brightness"] / 255 * 100)
        capabilities["brightness"] = {"type": "brightness", "percent": percent}

    if domain == "cover" and attributes.get("current_position") is not None:
        capabilities["position"] = {"type": "position", "percent_open": attributes["current_position"]}

    if domain == "sensor" and attributes.get("device_class") == "temperature" and ha_state is not None:
        try:
            capabilities["temperature"] = {"type": "temperature", "celsius": float(ha_state)}
        except ValueError:
            pass  # "unknown"/"unavailable" HA states - no reading to report

    if domain == "lock" and ha_state in ("locked", "unlocked"):
        # Transitional states ("locking"/"unlocking"/"jammed") are
        # deliberately not mapped to either boolean - "nicht erraten".
        capabilities["lock"] = {"type": "lock", "is_locked": ha_state == "locked"}

    if domain == "climate":
        mode = _HA_HVAC_MODE_TO_CLIMATE_MODE.get(attributes.get("hvac_mode") or ha_state)
        target = attributes.get("temperature")
        if mode is not None and target is not None:
            capabilities["climate"] = {"type": "climate", "target_celsius": float(target), "mode": mode}

    if domain == "camera" and ha_state not in (None, "unavailable", "unknown"):
        capabilities["camera_stream"] = {"type": "camera_stream", "is_available": True}

    return capabilities


def command_to_service_call(domain: str, command: dict) -> tuple[str, str, dict]:
    """Maps a SystemONE-shaped capability command dict (matching
    app.domain.capabilities.CapabilityCommand's discriminated-union JSON
    shape) to a Home Assistant (service_domain, service, extra_service_data)
    call. Raises CapabilityNotSupportedError for combinations with no
    known HA equivalent."""
    from .errors import CapabilityNotSupportedError

    capability_type = command.get("type")

    if capability_type == "on_off" and domain in ("light", "switch"):
        service = "turn_on" if command["is_on"] else "turn_off"
        return domain, service, {}

    if capability_type == "brightness" and domain == "light":
        # HA expects 0-255; SetBrightnessCommand.percent is 0-100.
        brightness = round(command["percent"] / 100 * 255)
        return "light", "turn_on", {"brightness": brightness}

    if capability_type == "position" and domain == "cover":
        return "cover", "set_cover_position", {"position": command["percent_open"]}

    if capability_type == "lock" and domain == "lock":
        return "lock", ("lock" if command["is_locked"] else "unlock"), {}

    if capability_type == "climate" and domain == "climate":
        return "climate", "set_temperature", {"temperature": command["target_celsius"], "hvac_mode": command["mode"]}

    raise CapabilityNotSupportedError(device_id="", capability=str(capability_type))
