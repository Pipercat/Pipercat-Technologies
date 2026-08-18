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

from typing import Any

from pydantic import TypeAdapter

from home_assistant_adapter import HomeAssistantAdapter
from home_assistant_adapter.errors import CapabilityNotSupportedError as HACapabilityNotSupportedError
from home_assistant_adapter.errors import DeviceNotFoundError as HADeviceNotFoundError
from home_assistant_adapter.errors import HomeAssistantAuthError, HomeAssistantConnectionError
from home_assistant_adapter.errors import TransientDeviceError as HATransientDeviceError

from app.domain.capabilities import CapabilityCommand, CapabilityState
from app.domain.device import DomainDevice
from app.domain.errors import CapabilityNotSupportedError, DeviceNotFoundError, TransientDeviceError


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


def _command_to_dict(command: CapabilityCommand) -> dict[str, Any]:
    return command.model_dump(mode="json")


def _dict_to_capability_state(raw_state: dict[str, Any]) -> CapabilityState:
    return TypeAdapter(CapabilityState).validate_python(raw_state)
