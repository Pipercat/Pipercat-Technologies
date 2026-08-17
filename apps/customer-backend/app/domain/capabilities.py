"""Stable, SystemONE-owned capability types (S1V2-02-002).

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


CapabilityState = Annotated[
    Union[OnOffState, BrightnessState, PositionState, TemperatureState],
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


# TemperatureState is read-only (a sensor reading) - deliberately no
# SetTemperatureCommand exists. Attempting to command it is a domain-level
# error, not just an adapter-level one (see DeviceService.send_command).
CapabilityCommand = Annotated[
    Union[SetOnOffCommand, SetBrightnessCommand, SetPositionCommand],
    Field(discriminator="type"),
]

COMMANDABLE_TYPES = {CapabilityType.ON_OFF, CapabilityType.BRIGHTNESS, CapabilityType.POSITION}
