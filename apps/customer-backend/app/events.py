"""Event model and internal event-bus boundary for live updates (S1V2-01-004,
extended with a real MQTT-backed implementation in S1V2-02-004).

No caller outside this module and app/events_mqtt.py may import an MQTT
client directly — everything goes through `EventBus`, mirroring the
HomeAssistantAdapter boundary pattern in services/home-assistant-adapter.
`InMemoryEventBus` is a dev/test stand-in only.
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field

EventHandler = Callable[["DeviceStateEvent"], Awaitable[None]]


class DeviceStateEvent(BaseModel):
    schemaVersion: int = 1
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

    @abstractmethod
    async def subscribe(self, handler: EventHandler) -> None:
        """Registers a handler invoked for every event published from now
        on. Not a replay mechanism — combine with recent() for late
        subscribers that also need history."""
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    """Dev/test stand-in. Not for production use — no persistence, no
    multi-process fan-out. See app/events_mqtt.py::MqttEventBus for the
    production implementation (S1V2-02-004); both satisfy this same
    contract."""

    _MAX_RETAINED = 500

    def __init__(self) -> None:
        self._events: list[DeviceStateEvent] = []
        self._handlers: list[EventHandler] = []

    async def publish(self, event: DeviceStateEvent) -> None:
        self._events.append(event)
        self._events = self._events[-self._MAX_RETAINED :]
        for handler in self._handlers:
            await handler(event)

    async def recent(self, limit: int = 50) -> list[DeviceStateEvent]:
        return list(reversed(self._events))[:limit]

    async def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)


event_bus: EventBus = InMemoryEventBus()
