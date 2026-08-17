"""Simulation adapter (S1V2-02-002): dev/test-only implementation of
DeviceAdapterPort, in the spirit of the existing Node.js pilot's
`lib/simulation.js`, but talking SystemONE's own typed capability model
instead of ad-hoc JSON.

Proves the Definition of Done directly: a simulated lamp is read/commanded
through DeviceService exactly like a real device will be once
HomeAssistantAdapter (S1V2-02-016 ff.) implements the same
DeviceAdapterPort shape - no domain/service code changes when that lands.
"""

import uuid

from .capabilities import (
    BrightnessState,
    CapabilityCommand,
    CapabilityType,
    OnOffState,
    PositionState,
    SetBrightnessCommand,
    SetOnOffCommand,
    SetPositionCommand,
)
from .device import DomainDevice
from .errors import CapabilityNotSupportedError, DeviceNotFoundError


class SimulationDeviceAdapter:
    def __init__(self) -> None:
        self._devices: dict[str, DomainDevice] = {}

    def seed_lamp(self, name: str = "Simulated Lamp", room_id: str | None = None) -> DomainDevice:
        device = DomainDevice(
            id=str(uuid.uuid4()),
            name=name,
            room_id=room_id,
            device_type="light",
            manufacturer_metadata={"vendor": "simulation", "model": "SystemONE-Sim-Lamp"},
            capabilities={
                CapabilityType.ON_OFF: OnOffState(is_on=False),
                CapabilityType.BRIGHTNESS: BrightnessState(percent=0),
            },
        )
        self._devices[device.id] = device
        return device

    async def list_devices(self) -> list[DomainDevice]:
        return list(self._devices.values())

    async def apply_command(self, device_id: str, command: CapabilityCommand):
        device = self._devices.get(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        if command.type not in device.capabilities:
            raise CapabilityNotSupportedError(device_id, command.type.value)

        if isinstance(command, SetOnOffCommand):
            new_state = OnOffState(is_on=command.is_on)
        elif isinstance(command, SetBrightnessCommand):
            new_state = BrightnessState(percent=command.percent)
        elif isinstance(command, SetPositionCommand):
            new_state = PositionState(percent_open=command.percent_open)
        else:  # pragma: no cover - exhaustive over CapabilityCommand's union
            raise CapabilityNotSupportedError(device_id, str(command.type))

        device.capabilities[command.type] = new_state
        return new_state
