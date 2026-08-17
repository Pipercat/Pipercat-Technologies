"""Domain service (S1V2-02-002). Orchestrates through DeviceAdapterPort -
never talks to an adapter's implementation details directly, so the same
service code works unmodified whether it's wired to SimulationDeviceAdapter
(this task) or the real HomeAssistantAdapter (S1V2-02-016 ff.)."""

from .adapter_port import DeviceAdapterPort
from .capabilities import CapabilityCommand
from .device import DomainDevice
from .errors import DeviceNotFoundError


class DeviceService:
    def __init__(self, adapter: DeviceAdapterPort) -> None:
        self._adapter = adapter

    async def list_devices(self) -> list[DomainDevice]:
        return await self._adapter.list_devices()

    async def get_device(self, device_id: str) -> DomainDevice:
        for device in await self._adapter.list_devices():
            if device.id == device_id:
                return device
        raise DeviceNotFoundError(device_id)

    async def send_command(self, device_id: str, command: CapabilityCommand):
        # Existence is re-checked here even though most adapters will also
        # check it, so DeviceNotFoundError is a reliable domain-level
        # contract regardless of adapter implementation quality.
        await self.get_device(device_id)
        return await self._adapter.apply_command(device_id, command)
