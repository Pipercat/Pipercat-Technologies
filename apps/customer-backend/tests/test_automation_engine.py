"""Domain-layer tests for the automation core model (S1V2-02-005): no
FastAPI, no HTTP, no Home Assistant - matches S1V2-02-002's precedent."""

from datetime import UTC, datetime

import pytest

from app.domain import (
    Automation,
    AutomationEngine,
    AutomationHistory,
    AutomationRunOutcome,
    AutomationValidationError,
    DeviceService,
)
from app.domain.automation_types import (
    Action,
    ComparisonOperator,
    DeviceStateCondition,
    DeviceStateTrigger,
    TimeTrigger,
)
from app.domain.capabilities import CapabilityType, SetBrightnessCommand, SetOnOffCommand
from app.domain.simulation_adapter import SimulationDeviceAdapter
from app.events import DeviceStateEvent


@pytest.fixture
def rig():
    adapter = SimulationDeviceAdapter()
    sensor = adapter.seed_lamp(name="Motion Sensor")  # reuses on_off/brightness shape for a simple test double
    lamp = adapter.seed_lamp(name="Hallway Lamp")
    service = DeviceService(adapter)
    engine = AutomationEngine(service, AutomationHistory(), retry_delay_seconds=0.001)
    return adapter, service, engine, sensor, lamp


def _if_then_automation(sensor_id: str, lamp_id: str, *, enabled: bool = True) -> Automation:
    return Automation(
        household_id="hh-1",
        name="Motion turns on hallway lamp",
        enabled=enabled,
        trigger=DeviceStateTrigger(
            condition=DeviceStateCondition(
                device_id=sensor_id,
                capability=CapabilityType.ON_OFF,
                field="is_on",
                operator=ComparisonOperator.EQUALS,
                value=True,
            )
        ),
        actions=[Action(device_id=lamp_id, command=SetOnOffCommand(is_on=True))],
    )


@pytest.mark.asyncio
async def test_simple_if_then(rig):
    _adapter, service, engine, sensor, lamp = rig
    automation = _if_then_automation(sensor.id, lamp.id)
    await engine.register(automation)

    event = DeviceStateEvent(type="device.state_changed", payload={"deviceId": sensor.id})
    # The trigger checks *current* device state, so set it before firing the event.
    await service.send_command(sensor.id, SetOnOffCommand(is_on=True))

    runs = await engine.on_device_event(event)

    assert len(runs) == 1
    assert runs[0].outcome == AutomationRunOutcome.SUCCESS
    lamp_state = (await service.get_device(lamp.id)).capabilities[CapabilityType.ON_OFF]
    assert lamp_state.is_on is True


@pytest.mark.asyncio
async def test_multiple_conditions_and_actions(rig):
    _adapter, service, engine, sensor, lamp = rig
    await service.send_command(sensor.id, SetOnOffCommand(is_on=True))
    await service.send_command(sensor.id, SetBrightnessCommand(percent=10))

    automation = Automation(
        household_id="hh-1",
        name="Dim hallway when dark and motion",
        trigger=TimeTrigger(at="07:00"),
        conditions=[
            DeviceStateCondition(
                device_id=sensor.id,
                capability=CapabilityType.ON_OFF,
                field="is_on",
                operator=ComparisonOperator.EQUALS,
                value=True,
            ),
            DeviceStateCondition(
                device_id=sensor.id,
                capability=CapabilityType.BRIGHTNESS,
                field="percent",
                operator=ComparisonOperator.BELOW,
                value=20,
            ),
        ],
        actions=[
            Action(device_id=lamp.id, command=SetOnOffCommand(is_on=True)),
            Action(device_id=lamp.id, command=SetBrightnessCommand(percent=40)),
        ],
    )
    await engine.register(automation)

    run = await engine.run(automation, reason="manual-test")

    assert run.outcome == AutomationRunOutcome.SUCCESS
    lamp_device = await service.get_device(lamp.id)
    assert lamp_device.capabilities[CapabilityType.ON_OFF].is_on is True
    assert lamp_device.capabilities[CapabilityType.BRIGHTNESS].percent == 40


@pytest.mark.asyncio
async def test_conditions_not_met_skips_actions(rig):
    _adapter, service, engine, sensor, lamp = rig
    await service.send_command(sensor.id, SetOnOffCommand(is_on=False))  # condition will fail

    automation = _if_then_automation(sensor.id, lamp.id)
    automation.conditions = [
        DeviceStateCondition(
            device_id=sensor.id,
            capability=CapabilityType.ON_OFF,
            field="is_on",
            operator=ComparisonOperator.EQUALS,
            value=True,
        )
    ]
    await engine.register(automation)

    run = await engine.run(automation, reason="manual-test")

    assert run.outcome == AutomationRunOutcome.SKIPPED_CONDITIONS_NOT_MET
    lamp_state = (await service.get_device(lamp.id)).capabilities[CapabilityType.ON_OFF]
    assert lamp_state.is_on is False  # action never ran


@pytest.mark.asyncio
async def test_time_trigger_fires_once_per_matching_minute(rig):
    _adapter, service, engine, sensor, lamp = rig
    automation = Automation(
        household_id="hh-1",
        name="Morning lamp",
        trigger=TimeTrigger(at="07:30"),
        actions=[Action(device_id=lamp.id, command=SetOnOffCommand(is_on=True))],
    )
    await engine.register(automation)

    matching_time = datetime(2026, 8, 18, 7, 30, tzinfo=UTC)
    first = await engine.check_time(matching_time)
    assert len(first) == 1
    assert first[0].outcome == AutomationRunOutcome.SUCCESS

    # Same minute again (e.g. a scheduler tick firing twice) - idempotent,
    # must not run a second time.
    second = await engine.check_time(matching_time.replace(second=45))
    assert second == []

    non_matching_time = datetime(2026, 8, 18, 7, 31, tzinfo=UTC)
    assert await engine.check_time(non_matching_time) == []


@pytest.mark.asyncio
async def test_disabled_automation_is_skipped(rig):
    _adapter, service, engine, sensor, lamp = rig
    automation = _if_then_automation(sensor.id, lamp.id, enabled=False)
    await engine.register(automation)

    run = await engine.run(automation, reason="manual-test")

    assert run.outcome == AutomationRunOutcome.SKIPPED_DISABLED
    lamp_state = (await service.get_device(lamp.id)).capabilities[CapabilityType.ON_OFF]
    assert lamp_state.is_on is False


@pytest.mark.asyncio
async def test_transient_error_is_retried_then_succeeds(rig):
    adapter, service, engine, sensor, lamp = rig
    adapter.inject_transient_fault(lamp.id, times=2)  # fails twice, succeeds on 3rd (max) attempt

    automation = _if_then_automation(sensor.id, lamp.id)
    await engine.register(automation)

    run = await engine.run(automation, reason="manual-test")

    assert run.outcome == AutomationRunOutcome.SUCCESS
    assert run.attempts == 3


@pytest.mark.asyncio
async def test_transient_error_exhausts_retries_and_fails(rig):
    adapter, service, engine, sensor, lamp = rig
    adapter.inject_transient_fault(lamp.id, times=10)  # always fails within the retry budget

    automation = _if_then_automation(sensor.id, lamp.id)
    await engine.register(automation)

    run = await engine.run(automation, reason="manual-test")

    assert run.outcome == AutomationRunOutcome.FAILED
    assert run.error_reason is not None
    assert engine.history(automation.id)[0].id == run.id


@pytest.mark.asyncio
async def test_permanent_error_is_not_retried(rig):
    _adapter, service, engine, sensor, lamp = rig
    automation = _if_then_automation(sensor.id, lamp.id)
    await engine.register(automation)
    # Remove the capability after registration to force a permanent
    # CapabilityNotSupportedError at execution time.
    device = await service.get_device(lamp.id)
    del device.capabilities[CapabilityType.ON_OFF]

    run = await engine.run(automation, reason="manual-test")

    assert run.outcome == AutomationRunOutcome.FAILED
    assert run.attempts == 1  # no retry for a permanent error


@pytest.mark.asyncio
async def test_validate_rejects_unknown_capability(rig):
    _adapter, service, engine, sensor, lamp = rig
    bad_automation = Automation(
        household_id="hh-1",
        name="Broken",
        trigger=TimeTrigger(at="08:00"),
        actions=[Action(device_id=lamp.id, command=SetBrightnessCommand(percent=1))],
    )
    # The seeded lamp does support brightness, so break it deliberately:
    device = await service.get_device(lamp.id)
    del device.capabilities[CapabilityType.BRIGHTNESS]

    with pytest.raises(AutomationValidationError):
        await engine.register(bad_automation)
