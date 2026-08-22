"""Wraps the real HomeAssistantAdapter to satisfy DeviceAdapterPort with
domain-shaped errors and types (S1V2-02-019).

`services/home-assistant-adapter` has zero internal dependencies (see
docs/architecture/repo-structure.md's import-boundary table) and cannot
import `app.domain.errors`/`app.domain.capabilities` - its own errors.py
and mapping.py therefore define self-contained, structurally-similar
error types and plain dicts instead (see that package's docstrings for
the full reasoning). `apps/customer-backend` is the one place allowed to
import `services/home-assistant-adapter` directly, so this is the single
translation point: every error the real adapter can raise is mapped to
its `app.domain.errors` equivalent here, and every plain dict it returns
is coerced into the real `DomainDevice`/`CapabilityState` Pydantic
models. Nothing above this module - `DeviceService`, `DeviceCommandService`,
API routes - ever sees a `home_assistant_adapter`-specific type.

"Timeouts und Servicefehler in standardisierte Fehler übersetzen"
(S1V2-02-019): connection/auth/timeout failures all become
`TransientDeviceError` - from the caller's perspective they're all
"the request didn't go through, retrying later might work", which is
exactly what that domain error already means (see app/domain/errors.py).
"""

from collections.abc import AsyncIterator
from typing import Any, Literal, TypedDict

from pydantic import TypeAdapter

from home_assistant_adapter import HomeAssistantAdapter
from home_assistant_adapter.errors import CapabilityNotSupportedError as HACapabilityNotSupportedError
from home_assistant_adapter.errors import DeviceNotFoundError as HADeviceNotFoundError
from home_assistant_adapter.errors import HomeAssistantAuthError, HomeAssistantConnectionError
from home_assistant_adapter.errors import TransientDeviceError as HATransientDeviceError

from app.domain.capabilities import CapabilityCommand, CapabilityState
from app.domain.device import DomainDevice
from app.domain.errors import CapabilityNotSupportedError, DeviceNotFoundError, TransientDeviceError


class ResyncEvent(TypedDict):
    kind: Literal["resync"]


class DeviceChangedEvent(TypedDict):
    kind: Literal["device_changed"]
    device: DomainDevice


LiveEvent = ResyncEvent | DeviceChangedEvent


class TranslatingHomeAssistantAdapter:
    """Structurally satisfies `app.domain.adapter_port.DeviceAdapterPort`
    by wrapping a real `HomeAssistantAdapter` instance."""

    def __init__(self, adapter: HomeAssistantAdapter) -> None:
        self._adapter = adapter

    async def list_devices(self) -> list[DomainDevice]:
        try:
            raw_devices = await self._adapter.list_devices()
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc
        return [DomainDevice(**device) for device in raw_devices]

    async def apply_command(self, device_id: str, command: CapabilityCommand) -> CapabilityState:
        try:
            raw_state = await self._adapter.apply_command(device_id, _command_to_dict(command))
        except HADeviceNotFoundError as exc:
            raise DeviceNotFoundError(device_id) from exc
        except HACapabilityNotSupportedError as exc:
            raise CapabilityNotSupportedError(device_id, exc.capability) from exc
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc
        return _dict_to_capability_state(raw_state)

    async def subscribe_events(self) -> AsyncIterator[LiveEvent]:
        """Translates `HomeAssistantAdapter.subscribe_events()`'s
        `{"kind": "resync"}` / `{"kind": "device_changed", "device": <dict>}`
        items (S1V2-02-020) the same way `list_devices()` does: raw dicts
        become real `DomainDevice` models, nothing above this module ever
        sees HA-shaped data. The `HomeAssistantConnectionError`/
        `HomeAssistantAuthError`/`TransientDeviceError` translation other
        methods do is intentionally *not* needed here - the underlying
        client already retries connection/auth/transient failures forever
        internally (see `home_assistant_adapter.ha_client`'s reconnect
        loop) and signals every successful (re)connect as a `resync` item
        instead of raising, so from this method's perspective those
        failures never surface as exceptions in the first place."""
        async for item in self._adapter.subscribe_events():
            if item["kind"] == "resync":
                yield {"kind": "resync"}
            else:
                yield {"kind": "device_changed", "device": DomainDevice(**item["device"])}

    async def start_zigbee_pairing(self, *, duration_seconds: int = 60) -> None:
        """S1V2-02-022: "Pairing über SystemONE anstoßen" - `zha.permit` is
        a real Home Assistant service, not a SystemONE invention (see
        `home_assistant_adapter.adapter.HomeAssistantAdapter.
        zha_permit_join`'s docstring for the source)."""
        try:
            await self._adapter.zha_permit_join(duration_seconds=duration_seconds)
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc

    async def remove_zigbee_device(self, *, ieee: str) -> None:
        try:
            await self._adapter.zha_remove_device(ieee=ieee)
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc

    async def list_zigbee_gateway_devices(self) -> list[dict[str, Any]]:
        """Raw passthrough, deliberately not coerced into a SystemONE type
        - see `HomeAssistantAdapter.zha_list_devices()`'s docstring for
        why this stays unprocessed pending real-hardware verification."""
        try:
            return await self._adapter.zha_list_devices()
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc

    async def start_matter_commissioning_with_code(self, *, code: str, network_only: bool = True) -> None:
        """S1V2-02-023: `matter/commission` is a real Home Assistant
        command (see `HomeAssistantAdapter.matter_commission_with_code()`'s
        docstring for the source), not a SystemONE invention."""
        try:
            await self._adapter.matter_commission_with_code(code=code, network_only=network_only)
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc

    async def start_matter_commissioning_on_network(self, *, pin: int, ip_addr: str | None = None) -> None:
        try:
            await self._adapter.matter_commission_on_network(pin=pin, ip_addr=ip_addr)
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc

    async def remove_matter_device(self, *, device_id: str, fabric_index: int) -> None:
        """`device_id` is the SystemONE device id - resolved to Home
        Assistant's own device-registry id internally, so callers never
        need to know that distinction exists (mirrors how
        `remove_zigbee_device()` instead takes a caller-supplied `ieee`,
        since Zigbee's equivalent resolution isn't safely buildable yet -
        see docs/architecture/matter-integration.md for why Matter's case
        is different)."""
        try:
            ha_device_id = await self._adapter.resolve_ha_device_id(device_id)
            if ha_device_id is None:
                raise DeviceNotFoundError(device_id)
            await self._adapter.matter_remove_fabric(ha_device_id=ha_device_id, fabric_index=fabric_index)
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc

    async def get_matter_node_diagnostics(self, *, device_id: str) -> dict[str, Any]:
        """Raw passthrough (see `HomeAssistantAdapter.matter_node_diagnostics()`'s
        docstring) - used to discover a device's current `fabric_index`
        values before calling `remove_matter_device()`."""
        try:
            ha_device_id = await self._adapter.resolve_ha_device_id(device_id)
            if ha_device_id is None:
                raise DeviceNotFoundError(device_id)
            return await self._adapter.matter_node_diagnostics(ha_device_id=ha_device_id)
        except (HomeAssistantConnectionError, HomeAssistantAuthError, HATransientDeviceError) as exc:
            raise TransientDeviceError(str(exc)) from exc


def _command_to_dict(command: CapabilityCommand) -> dict[str, Any]:
    return command.model_dump(mode="json")


def _dict_to_capability_state(raw_state: dict[str, Any]) -> CapabilityState:
    return TypeAdapter(CapabilityState).validate_python(raw_state)
