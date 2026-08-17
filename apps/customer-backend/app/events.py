"""Event model and internal event-bus boundary for live updates (S1V2-01-004).

Production is backed by MQTT (S1V2-02-004), but no caller outside this
module may import an MQTT client directly — everything goes through
`EventBus`, mirroring the HomeAssistantAdapter boundary pattern in
services/home-assistant-adapter. `InMemoryEventBus` is a dev/test stand-in
only.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class DeviceStateEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    occurredAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlationId: str | None = None
    payload: dict


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: DeviceStateEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    async def recent(self, limit: int = 50) -> list[DeviceStateEvent]:
        """Most recent events first."""
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    """Dev/test stand-in. Not for production use — no persistence, no
    multi-process fan-out. Replaced by an MQTT-backed implementation in
    S1V2-02-004 without changing this class's public contract."""

    _MAX_RETAINED = 500

    def __init__(self) -> None:
        self._events: list[DeviceStateEvent] = []

    async def publish(self, event: DeviceStateEvent) -> None:
        self._events.append(event)
        self._events = self._events[-self._MAX_RETAINED :]

    async def recent(self, limit: int = 50) -> list[DeviceStateEvent]:
        return list(reversed(self._events))[:limit]


event_bus: EventBus = InMemoryEventBus()
