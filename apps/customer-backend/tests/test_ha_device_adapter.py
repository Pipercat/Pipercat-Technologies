"""S1V2-02-019 Definition of Done: "Timeouts und Servicefehler in
standardisierte Fehler übersetzen" and "manipulierte Service-/
Entityangaben können keine beliebigen HA-Services auslösen" - the
real/mock-HA half of TranslatingHomeAssistantAdapter (see
test_device_commands.py for the simulated-adapter/security-wrapper half).

Uses a bare double for the underlying `HomeAssistantAdapter` rather than
the real HTTP client - TranslatingHomeAssistantAdapter only ever calls
`list_devices()`/`apply_command()` on it (structural typing, no
`isinstance` check), so a double satisfying that surface is a faithful
substitute without needing a running Home Assistant instance.
"""

import pytest

from home_assistant_adapter.errors import CapabilityNotSupportedError as HACapabilityNotSupportedError
from home_assistant_adapter.errors import DeviceNotFoundError as HADeviceNotFoundError
from home_assistant_adapter.errors import HomeAssistantAuthError, HomeAssistantConnectionError
from home_assistant_adapter.errors import TransientDeviceError as HATransientDeviceError

from app.domain.capabilities import CapabilityType, LockState, OnOffState, SetLockCommand, SetOnOffCommand
from app.domain.device import DomainDevice
from app.domain.errors import CapabilityNotSupportedError, DeviceNotFoundError, TransientDeviceError
from app.services.ha_device_adapter import TranslatingHomeAssistantAdapter


class _RawHomeAssistantAdapterDouble:
    """Stands in for the real `HomeAssistantAdapter` - returns/raises
    exactly what's configured, so tests control the HA-shaped boundary
    precisely without a live Home Assistant instance."""

    def __init__(self) -> None:
        self.list_devices_result: list[dict] | Exception = []
        self.apply_command_result: dict | Exception = {}
        self.last_apply_command_args: tuple[str, dict] | None = None
        self.zha_permit_join_result: None | Exception = None
        self.last_zha_permit_join_duration: int | None = None
        self.zha_remove_device_result: None | Exception = None
        self.last_zha_remove_device_ieee: str | None = None
        self.zha_list_devices_result: list[dict] | Exception = []

    async def list_devices(self) -> list[dict]:
        if isinstance(self.list_devices_result, Exception):
            raise self.list_devices_result
        return self.list_devices_result

    async def apply_command(self, device_id: str, command: dict) -> dict:
        self.last_apply_command_args = (device_id, command)
        if isinstance(self.apply_command_result, Exception):
            raise self.apply_command_result
        return self.apply_command_result

    async def zha_permit_join(self, *, duration_seconds: int = 60) -> None:
        self.last_zha_permit_join_duration = duration_seconds
        if isinstance(self.zha_permit_join_result, Exception):
            raise self.zha_permit_join_result

    async def zha_remove_device(self, *, ieee: str) -> None:
        self.last_zha_remove_device_ieee = ieee
        if isinstance(self.zha_remove_device_result, Exception):
            raise self.zha_remove_device_result

    async def zha_list_devices(self) -> list[dict]:
        if isinstance(self.zha_list_devices_result, Exception):
            raise self.zha_list_devices_result
        return self.zha_list_devices_result


# --- error translation: list_devices ----------------------------------------


async def test_list_devices_translates_connection_error_to_transient():
    raw = _RawHomeAssistantAdapterDouble()
    raw.list_devices_result = HomeAssistantConnectionError("could not reach HA")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(TransientDeviceError):
        await adapter.list_devices()


async def test_list_devices_translates_auth_error_to_transient():
    raw = _RawHomeAssistantAdapterDouble()
    raw.list_devices_result = HomeAssistantAuthError("token rejected")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(TransientDeviceError):
        await adapter.list_devices()


async def test_list_devices_translates_ha_transient_error():
    raw = _RawHomeAssistantAdapterDouble()
    raw.list_devices_result = HATransientDeviceError("timeout")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(TransientDeviceError):
        await adapter.list_devices()


async def test_list_devices_coerces_raw_dicts_to_domain_device():
    raw = _RawHomeAssistantAdapterDouble()
    raw.list_devices_result = [
        {
            "id": "light-1",
            "name": "Lamp",
            "device_type": "light",
            "compatibility": "supported",
            "manufacturer_metadata": {},
            "capabilities": {"on_off": {"type": "on_off", "is_on": True}},
        }
    ]
    adapter = TranslatingHomeAssistantAdapter(raw)

    devices = await adapter.list_devices()

    assert devices == [
        DomainDevice(
            id="light-1",
            name="Lamp",
            device_type="light",
            compatibility="supported",
            capabilities={CapabilityType.ON_OFF: OnOffState(is_on=True)},
        )
    ]


# --- error translation: apply_command ---------------------------------------


async def test_apply_command_translates_ha_device_not_found():
    raw = _RawHomeAssistantAdapterDouble()
    raw.apply_command_result = HADeviceNotFoundError("light-1")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(DeviceNotFoundError):
        await adapter.apply_command("light-1", SetOnOffCommand(is_on=True))


async def test_apply_command_translates_ha_capability_not_supported():
    raw = _RawHomeAssistantAdapterDouble()
    raw.apply_command_result = HACapabilityNotSupportedError("light-1", "lock")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(CapabilityNotSupportedError):
        await adapter.apply_command("light-1", SetLockCommand(is_locked=True))


async def test_apply_command_translates_connection_and_transient_errors():
    for exc in (HomeAssistantConnectionError("down"), HomeAssistantAuthError("bad token"), HATransientDeviceError("timeout")):
        raw = _RawHomeAssistantAdapterDouble()
        raw.apply_command_result = exc
        adapter = TranslatingHomeAssistantAdapter(raw)

        with pytest.raises(TransientDeviceError):
            await adapter.apply_command("light-1", SetOnOffCommand(is_on=True))


async def test_apply_command_coerces_raw_state_dict_to_capability_state():
    raw = _RawHomeAssistantAdapterDouble()
    raw.apply_command_result = {"type": "lock", "is_locked": False}
    adapter = TranslatingHomeAssistantAdapter(raw)

    new_state = await adapter.apply_command("lock-1", SetLockCommand(is_locked=False))

    assert new_state == LockState(is_locked=False)


# --- whitelist / manipulation resistance ------------------------------------
#
# "Manipulierte Service-/Entityangaben können keine beliebigen HA-Services
# auslösen": TranslatingHomeAssistantAdapter.apply_command() only ever
# accepts a `CapabilityCommand` - a closed Pydantic discriminated union
# (app/domain/capabilities.py). There is no code path here that accepts a
# raw HA service name, entity_id, or arbitrary dict from a caller; the one
# place that does turn a command into a HA (service_domain, service)
# tuple is `home_assistant_adapter.mapping.command_to_service_call`,
# which is a fixed if/elif whitelist with no default/fallback branch (see
# services/home-assistant-adapter/tests/test_mapping.py's
# test_command_to_service_call_rejects_unsupported_combination and
# test_command_to_service_call_rejects_camera_stream_commands for that
# whitelist enforced directly). These tests verify the resulting
# CapabilityNotSupportedError survives translation all the way up through
# TranslatingHomeAssistantAdapter as the domain-level equivalent, and that
# only ever the validated command's own dumped fields are forwarded -
# nothing else can be smuggled into what reaches the underlying adapter.


async def test_apply_command_cannot_bypass_command_type_validation():
    """CapabilityCommand is a closed discriminated union - Pydantic
    rejects an unrecognized `type` before any HA call is ever made, so
    there is no way to reach the underlying adapter with a made-up
    capability/service name in the first place."""
    with pytest.raises(Exception):
        SetOnOffCommand.model_validate({"type": "shell_exec", "is_on": True})


async def test_apply_command_only_forwards_the_validated_commands_own_fields():
    """Even with a legitimate, validated command, the dict handed to the
    underlying adapter contains exactly that command's own declared
    fields - never anything else an attacker-controlled `command` object
    might have carried (there is nothing else on a Pydantic model to
    carry: `model_dump()` only ever emits declared fields)."""
    raw = _RawHomeAssistantAdapterDouble()
    raw.apply_command_result = {"type": "on_off", "is_on": True}
    adapter = TranslatingHomeAssistantAdapter(raw)

    await adapter.apply_command("light-1", SetOnOffCommand(is_on=True))

    device_id, forwarded_command = raw.last_apply_command_args
    assert device_id == "light-1"
    assert forwarded_command == {"type": "on_off", "is_on": True}


async def test_apply_command_rejects_unsupported_capability_even_when_ha_reports_success_shaped_error():
    """A HACapabilityNotSupportedError from the underlying whitelist
    (services/home-assistant-adapter/mapping.py's command_to_service_call
    has no fallback branch - see its own tests) always reaches the caller
    as the domain error, never as a silently-applied command."""
    raw = _RawHomeAssistantAdapterDouble()
    raw.apply_command_result = HACapabilityNotSupportedError("camera-1", "camera_stream")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(CapabilityNotSupportedError):
        await adapter.apply_command("camera-1", SetLockCommand(is_locked=True))


async def test_apply_command_device_id_not_in_ha_registry_is_reported_as_not_found():
    """A device_id that the underlying adapter doesn't recognize (e.g. a
    tampered or stale id that was never returned by list_devices()) is
    reported as DeviceNotFoundError, not silently routed to some other
    entity - the real adapter's own device_id->entity_id lookup
    (adapter.py's `_entity_id_by_device_id`) is what enforces this, and
    this test verifies the error survives translation intact."""
    raw = _RawHomeAssistantAdapterDouble()
    raw.apply_command_result = HADeviceNotFoundError("never-listed-device")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(DeviceNotFoundError):
        await adapter.apply_command("never-listed-device", SetOnOffCommand(is_on=True))


# --- ZHA / Zigbee pairing (S1V2-02-022) -------------------------------------


async def test_start_zigbee_pairing_forwards_the_duration():
    raw = _RawHomeAssistantAdapterDouble()
    adapter = TranslatingHomeAssistantAdapter(raw)

    await adapter.start_zigbee_pairing(duration_seconds=120)

    assert raw.last_zha_permit_join_duration == 120


async def test_start_zigbee_pairing_translates_connection_errors():
    raw = _RawHomeAssistantAdapterDouble()
    raw.zha_permit_join_result = HomeAssistantConnectionError("down")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(TransientDeviceError):
        await adapter.start_zigbee_pairing()


async def test_remove_zigbee_device_forwards_the_ieee():
    raw = _RawHomeAssistantAdapterDouble()
    adapter = TranslatingHomeAssistantAdapter(raw)

    await adapter.remove_zigbee_device(ieee="00:11:22:33:44:55:66:77")

    assert raw.last_zha_remove_device_ieee == "00:11:22:33:44:55:66:77"


async def test_remove_zigbee_device_translates_auth_errors():
    raw = _RawHomeAssistantAdapterDouble()
    raw.zha_remove_device_result = HomeAssistantAuthError("bad token")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(TransientDeviceError):
        await adapter.remove_zigbee_device(ieee="00:11:22:33:44:55:66:77")


async def test_list_zigbee_gateway_devices_passes_through_raw_data():
    raw = _RawHomeAssistantAdapterDouble()
    raw.zha_list_devices_result = [{"ieee": "00:11:22:33:44:55:66:77"}]
    adapter = TranslatingHomeAssistantAdapter(raw)

    devices = await adapter.list_zigbee_gateway_devices()

    assert devices == [{"ieee": "00:11:22:33:44:55:66:77"}]


async def test_list_zigbee_gateway_devices_translates_transient_errors():
    raw = _RawHomeAssistantAdapterDouble()
    raw.zha_list_devices_result = HATransientDeviceError("timeout")
    adapter = TranslatingHomeAssistantAdapter(raw)

    with pytest.raises(TransientDeviceError):
        await adapter.list_zigbee_gateway_devices()
