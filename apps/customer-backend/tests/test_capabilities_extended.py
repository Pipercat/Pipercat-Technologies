"""S1V2-02-018: pure Pydantic-model tests for the capability types added
alongside the HA mapping layer (lock/climate/camera). No FastAPI, no HTTP,
no Home Assistant - matches test_domain_device.py's "Domain-Tests laufen
ohne Home Assistant" pattern. SimulationDeviceAdapter is not extended for
these types (out of scope for this task), so these tests exercise the
Pydantic models directly rather than through DeviceService.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.capabilities import (
    CameraStreamState,
    CapabilityCommand,
    CapabilityState,
    CapabilityType,
    ClimateMode,
    ClimateState,
    COMMANDABLE_TYPES,
    LockState,
    SetClimateCommand,
    SetLockCommand,
)


def test_lock_state_round_trips_through_the_capability_state_union():
    state = TypeAdapter(CapabilityState).validate_python({"type": "lock", "is_locked": True})
    assert isinstance(state, LockState)
    assert state.is_locked is True


def test_climate_state_round_trips_through_the_capability_state_union():
    state = TypeAdapter(CapabilityState).validate_python(
        {"type": "climate", "target_celsius": 21.5, "mode": "heat"}
    )
    assert isinstance(state, ClimateState)
    assert state.mode == ClimateMode.HEAT


def test_camera_stream_state_round_trips_through_the_capability_state_union():
    state = TypeAdapter(CapabilityState).validate_python({"type": "camera_stream", "is_available": True})
    assert isinstance(state, CameraStreamState)


def test_climate_mode_rejects_a_value_outside_the_normalized_set():
    """"nicht erraten" at the type level too - "dry"/"fan_only" are not
    valid ClimateMode values, so a command carrying one is rejected before
    any domain logic runs (mirrors how SetBrightnessCommand already
    rejects out-of-range percentages)."""
    with pytest.raises(ValidationError):
        SetClimateCommand(target_celsius=21.0, mode="fan_only")


def test_lock_and_climate_are_commandable():
    assert CapabilityType.LOCK in COMMANDABLE_TYPES
    assert CapabilityType.CLIMATE in COMMANDABLE_TYPES


def test_camera_stream_is_deliberately_not_commandable():
    """Read-only, like TEMPERATURE - only ever reports availability, never
    a stream URL/credential, and never accepts a command."""
    assert CapabilityType.CAMERA_STREAM not in COMMANDABLE_TYPES
    assert CapabilityType.TEMPERATURE not in COMMANDABLE_TYPES


def test_camera_stream_has_no_corresponding_command_type():
    # No SetCameraStreamCommand class exists at all - proven structurally
    # by CapabilityCommand rejecting a camera_stream-typed payload outright.
    with pytest.raises(ValidationError):
        TypeAdapter(CapabilityCommand).validate_python({"type": "camera_stream", "is_available": True})


def test_lock_command_round_trips_through_the_capability_command_union():
    command = TypeAdapter(CapabilityCommand).validate_python({"type": "lock", "is_locked": False})
    assert isinstance(command, SetLockCommand)
    assert command.is_locked is False
