class DeviceNotFoundError(LookupError):
    def __init__(self, device_id: str) -> None:
        super().__init__(f"Device '{device_id}' not found")
        self.device_id = device_id


class CapabilityNotSupportedError(ValueError):
    def __init__(self, device_id: str, capability: str) -> None:
        super().__init__(f"Device '{device_id}' does not support capability '{capability}'")
        self.device_id = device_id
        self.capability = capability
