"""Automation core model types (S1V2-02-005).

Trigger/condition comparisons reuse the operator set already proven in the
existing Node.js pilot (mvp/systemone-pi/lib/automations.js: "equals,
notEquals, above, below") for continuity, translated into SystemONE's own
typed capability model (S1V2-02-002) instead of ad-hoc JSON.
"""

import uuid
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from .capabilities import CapabilityCommand, CapabilityType


class ComparisonOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    ABOVE = "above"
    BELOW = "below"


class DeviceStateCondition(BaseModel):
    """Also doubles as a device-state *trigger* definition (DeviceStateTrigger
    below) - "fires/holds when this device's capability field compares this
    way" is the same shape whether checked once (condition) or watched for
    changes (trigger)."""

    type: Literal["device_state"] = "device_state"
    device_id: str
    capability: CapabilityType
    field: str  # e.g. "is_on", "percent", "celsius" - the attribute within the capability state
    operator: ComparisonOperator
    value: bool | int | float


class DeviceStateTrigger(BaseModel):
    type: Literal["device_state"] = "device_state"
    condition: DeviceStateCondition


class TimeTrigger(BaseModel):
    type: Literal["time"] = "time"
    at: str = Field(pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")  # "HH:MM", 24h


class SunEventTrigger(BaseModel):
    type: Literal["sun_event"] = "sun_event"
    event: Literal["sunrise", "sunset"]
    offset_minutes: int = 0


Trigger = Annotated[Union[DeviceStateTrigger, TimeTrigger, SunEventTrigger], Field(discriminator="type")]


class Action(BaseModel):
    device_id: str
    command: CapabilityCommand


class Automation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    household_id: str
    name: str
    enabled: bool = True
    trigger: Trigger
    conditions: list[DeviceStateCondition] = Field(default_factory=list)
    actions: list[Action]


def evaluate_comparison(actual: bool | int | float, operator: ComparisonOperator, expected: bool | int | float) -> bool:
    if operator is ComparisonOperator.EQUALS:
        return actual == expected
    if operator is ComparisonOperator.NOT_EQUALS:
        return actual != expected
    if operator is ComparisonOperator.ABOVE:
        return actual > expected
    if operator is ComparisonOperator.BELOW:
        return actual < expected
    raise ValueError(f"Unknown operator: {operator}")  # pragma: no cover - exhaustive enum
