"""Stable, SystemONE-owned capability types (S1V2-02-002, extended in
S1V2-02-018 for locks/climate/camera).

SystemONE never depends on Home Assistant's entity/domain/service
vocabulary directly. This module is that boundary: every device the
domain layer knows about speaks exclusively in these typed states and
commands, regardless of which adapter (Home Assistant, a future direct
adapter, or the simulation adapter used here and in tests) produced them.
"""

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class CapabilityType(str, Enum):
    ON_OFF = "on_off"
    BRIGHTNESS = "brightness"
    POSITION = "position"  # covers/blinds, 0 = closed, 100 = open
    TEMPERATURE = "temperature"  # read-only sensor reading
    LOCK = "lock"
    CLIMATE = "climate"
    CAMERA_STREAM = "camera_stream"  # read-only: whether a live feed exists, never the feed itself


class OnOffState(BaseModel):
    type: Literal[CapabilityType.ON_OFF] = CapabilityType.ON_OFF
    is_on: bool


class BrightnessState(BaseModel):
    type: Literal[CapabilityType.BRIGHTNESS] = CapabilityType.BRIGHTNESS
    percent: int = Field(ge=0, le=100)


class PositionState(BaseModel):
    type: Literal[CapabilityType.POSITION] = CapabilityType.POSITION
    percent_open: int = Field(ge=0, le=100)


class TemperatureState(BaseModel):
    type: Literal[CapabilityType.TEMPERATURE] = CapabilityType.TEMPERATURE
    celsius: float


class LockState(BaseModel):
    type: Literal[CapabilityType.LOCK] = CapabilityType.LOCK
    is_locked: bool


class ClimateMode(str, Enum):
    """Deliberately only the handful of HVAC modes SystemONE actually
    normalizes to - an HA mode outside this set (e.g. "dry", "fan_only",
    "heat_cool") is not guessed into the closest match, it makes the
    whole entity unsupported instead (see mapping.py)."""

    OFF = "off"
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"


class ClimateState(BaseModel):
    type: Literal[CapabilityType.CLIMATE] = CapabilityType.CLIMATE
    target_celsius: float
    mode: ClimateMode


class CameraStreamState(BaseModel):
    type: Literal[CapabilityType.CAMERA_STREAM] = CapabilityType.CAMERA_STREAM
    is_available: bool


CapabilityState = Annotated[
    Union[OnOffState, BrightnessState, PositionState, TemperatureState, LockState, ClimateState, CameraStreamState],
    Field(discriminator="type"),
]


class SetOnOffCommand(BaseModel):
    type: Literal[CapabilityType.ON_OFF] = CapabilityType.ON_OFF
    is_on: bool


class SetBrightnessCommand(BaseModel):
    type: Literal[CapabilityType.BRIGHTNESS] = CapabilityType.BRIGHTNESS
    percent: int = Field(ge=0, le=100)


class SetPositionCommand(BaseModel):
    type: Literal[CapabilityType.POSITION] = CapabilityType.POSITION
    percent_open: int = Field(ge=0, le=100)


class SetLockCommand(BaseModel):
    type: Literal[CapabilityType.LOCK] = CapabilityType.LOCK
    is_locked: bool


class SetClimateCommand(BaseModel):
    type: Literal[CapabilityType.CLIMATE] = CapabilityType.CLIMATE
    target_celsius: float
    mode: ClimateMode


# TemperatureState and CameraStreamState are read-only (a sensor reading
# and "does a live feed exist", respectively) - deliberately no Set*Command
# exists for either. Attempting to command one is a domain-level error,
# not just an adapter-level one (see DeviceService.send_command). Camera
# viewing/recording itself is a separate, security-sensitive future task
# (a protected action, per S1V2-02-012's pattern) - this capability only
# ever reports availability, never a stream URL or credential.
CapabilityCommand = Annotated[
    Union[SetOnOffCommand, SetBrightnessCommand, SetPositionCommand, SetLockCommand, SetClimateCommand],
    Field(discriminator="type"),
]

COMMANDABLE_TYPES = {
    CapabilityType.ON_OFF,
    CapabilityType.BRIGHTNESS,
    CapabilityType.POSITION,
    CapabilityType.LOCK,
    CapabilityType.CLIMATE,
}
