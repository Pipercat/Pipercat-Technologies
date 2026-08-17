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
    """Raised by an adapter (real or simulated) for a failure that is
    plausibly worth retrying (timeout, temporary unreachability) - as
    opposed to DeviceNotFoundError/CapabilityNotSupportedError, which are
    permanent and must never be retried (S1V2-02-005: "sichere
    Retry-Regeln")."""
