"""Pure domain-layer tests (S1V2-02-002): no FastAPI, no HTTP, no Home
Assistant anywhere in this file - proves "Domain-Tests laufen ohne Home
Assistant"."""

import pytest
from pydantic import ValidationError

from app.domain import CapabilityNotSupportedError, DeviceNotFoundError, DeviceService
from app.domain.capabilities import (
    BrightnessState,
    CapabilityType,
    OnOffState,
    SetBrightnessCommand,
    SetOnOffCommand,
)
from app.domain.simulation_adapter import SimulationDeviceAdapter


@pytest.fixture
def service():
    adapter = SimulationDeviceAdapter()
    lamp = adapter.seed_lamp(name="Test Lamp")
    return DeviceService(adapter), lamp


@pytest.mark.asyncio
async def test_simulated_lamp_starts_off(service):
    device_service, lamp = service
    device = await device_service.get_device(lamp.id)
    assert device.capabilities[CapabilityType.ON_OFF] == OnOffState(is_on=False)


@pytest.mark.asyncio
async def test_turning_on_the_simulated_lamp_updates_state(service):
    device_service, lamp = service
    new_state = await device_service.send_command(lamp.id, SetOnOffCommand(is_on=True))
    assert new_state == OnOffState(is_on=True)

    device = await device_service.get_device(lamp.id)
    assert device.capabilities[CapabilityType.ON_OFF].is_on is True


@pytest.mark.asyncio
async def test_setting_brightness_updates_state(service):
    device_service, lamp = service
    new_state = await device_service.send_command(lamp.id, SetBrightnessCommand(percent=80))
    assert new_state == BrightnessState(percent=80)


@pytest.mark.asyncio
async def test_out_of_range_brightness_is_rejected_by_the_typed_command():
    with pytest.raises(ValidationError):
        SetBrightnessCommand(percent=150)


@pytest.mark.asyncio
async def test_unknown_device_raises_domain_error(service):
    device_service, _lamp = service
    with pytest.raises(DeviceNotFoundError):
        await device_service.get_device("does-not-exist")


@pytest.mark.asyncio
async def test_manufacturer_metadata_is_present_but_opaque(service):
    _device_service, lamp = service
    assert lamp.manufacturer_metadata["vendor"] == "simulation"


class _NoCommandsAdapter(SimulationDeviceAdapter):
    """A device whose capabilities dict is empty, to exercise the
    'capability not supported' path independent of a specific type."""


@pytest.mark.asyncio
async def test_unsupported_capability_raises_domain_error():
    adapter = _NoCommandsAdapter()
    lamp = adapter.seed_lamp()
    lamp.capabilities.clear()  # simulate a device that only supports ON_OFF via HA, no BRIGHTNESS
    service = DeviceService(adapter)

    with pytest.raises(CapabilityNotSupportedError):
        await service.send_command(lamp.id, SetOnOffCommand(is_on=True))
