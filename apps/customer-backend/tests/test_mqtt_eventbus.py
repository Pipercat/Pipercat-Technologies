"""Integration tests against a real local Mosquitto broker (S1V2-02-004
Definition of Done: "Integrationstest mit Broker-Neustart, Duplicate Event
und Netzverlust; Systemzustand bleibt konsistent")."""

import asyncio

import pytest

from app.events import DeviceStateEvent
from app.events_mqtt import MqttEventBus
from tests.mqtt_conftest import requires_mosquitto, test_broker  # noqa: F401

pytestmark = requires_mosquitto


async def _wait_for(predicate, timeout: float = 3.0, interval: float = 0.05) -> bool:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return False


def _collector():
    """EventBus.subscribe() requires an async handler (EventHandler =
    Callable[[DeviceStateEvent], Awaitable[None]]) - list.append is sync
    and must not be passed directly."""
    received: list[DeviceStateEvent] = []

    async def handler(event: DeviceStateEvent) -> None:
        received.append(event)

    return received, handler


@pytest.fixture
async def bus(test_broker):
    event_bus = MqttEventBus(hostname="127.0.0.1", port=test_broker.port, reconnect_delay=0.5)
    await event_bus.start()
    assert await _wait_for(lambda: event_bus.connected.is_set()), "bus never connected to test broker"
    yield event_bus, test_broker
    await event_bus.stop()


async def test_publish_and_receive_roundtrip(bus):
    event_bus, _broker = bus
    received, handler = _collector()
    await event_bus.subscribe(handler)

    event = DeviceStateEvent(type="device.state_changed", payload={"foo": "bar"})
    await event_bus.publish(event)

    assert await _wait_for(lambda: len(received) == 1)
    assert received[0].id == event.id
    assert received[0].schemaVersion == 1

    recent = await event_bus.recent()
    assert recent[0].id == event.id


async def test_duplicate_event_id_is_deduplicated(bus):
    event_bus, _broker = bus
    received, handler = _collector()
    await event_bus.subscribe(handler)

    event = DeviceStateEvent(id="duplicate-test-id", type="device.state_changed", payload={})
    await event_bus.publish(event)
    assert await _wait_for(lambda: len(received) == 1)

    # Same event id again - simulates QoS-1 redelivery after a broker
    # restart or a client retrying a publish it wasn't sure succeeded.
    await event_bus.publish(event)
    await asyncio.sleep(0.3)  # give a wrongly-duplicated delivery a chance to show up

    assert len(received) == 1
    recent = await event_bus.recent(limit=10)
    assert sum(1 for e in recent if e.id == "duplicate-test-id") == 1


async def test_broker_restart_queues_then_flushes_without_crashing(bus):
    event_bus, broker = bus
    received, handler = _collector()
    await event_bus.subscribe(handler)

    broker.stop()
    assert await _wait_for(lambda: not event_bus.connected.is_set(), timeout=5.0)

    offline_event = DeviceStateEvent(type="device.offline_test", payload={})
    await event_bus.publish(offline_event)  # must not raise despite the broker being down
    assert event_bus.outbox_size == 1

    broker.start()
    assert await _wait_for(lambda: event_bus.connected.is_set(), timeout=10.0)
    assert await _wait_for(lambda: event_bus.outbox_size == 0, timeout=5.0)
    assert await _wait_for(lambda: any(e.id == offline_event.id for e in received), timeout=5.0)

    # System stays consistent after the outage: a normal publish still works.
    followup = DeviceStateEvent(type="device.after_restart", payload={})
    await event_bus.publish(followup)
    assert await _wait_for(lambda: any(e.id == followup.id for e in received), timeout=5.0)
