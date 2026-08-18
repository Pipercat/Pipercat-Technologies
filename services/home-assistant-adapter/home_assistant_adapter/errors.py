"""Adapter-local error types (S1V2-02-016).

Deliberately self-contained, not imported from `apps/customer-backend`'s
`app/domain/errors.py` - this package has zero internal dependencies (see
docs/architecture/repo-structure.md's import-boundary table: "services/
home-assistant-adapter: keine internen Abhängigkeiten"). Names mirror the
domain layer's error shapes on purpose so that whoever wires a
HomeAssistantAdapter into `apps/customer-backend` (a forward import that
*is* allowed) has an obvious, narrow translation to perform at that one
call site, rather than this package reaching backwards across the
boundary itself.
"""


class HomeAssistantConnectionError(RuntimeError):
    """Could not reach Home Assistant at all (DNS/connect/timeout) - the
    adapter's general transient-failure signal."""


class HomeAssistantAuthError(RuntimeError):
    """The configured access token was rejected."""


class DeviceNotFoundError(LookupError):
    def __init__(self, device_id: str) -> None:
        super().__init__(f"Device '{device_id}' not found")
        self.device_id = device_id


class CapabilityNotSupportedError(ValueError):
    def __init__(self, device_id: str, capability: str) -> None:
        super().__init__(f"Device '{device_id}' does not support capability '{capability}'")
        self.device_id = device_id
        self.capability = capability


class TransientDeviceError(RuntimeError):
    """A single command/request failed in a plausibly-retryable way
    (timeout, temporary unreachability) - as opposed to
    DeviceNotFoundError/CapabilityNotSupportedError, which are permanent."""
