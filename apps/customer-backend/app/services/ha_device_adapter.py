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


def _command_to_dict(command: CapabilityCommand) -> dict[str, Any]:
    return command.model_dump(mode="json")


def _dict_to_capability_state(raw_state: dict[str, Any]) -> CapabilityState:
    return TypeAdapter(CapabilityState).validate_python(raw_state)
