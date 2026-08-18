"""S1V2-02-020 Definition of Done: "HA-Neustart und Netzunterbrechung
führen nach Wiederverbindung zu konsistentem SystemONE-Zustand."

Uses a bare double for `TranslatingHomeAssistantAdapter` (only
`subscribe_events()`/`list_devices()` are called - structural typing, no
`isinstance` check) so the ingestion loop's resync/diff/publish logic is
tested without any real or mocked Home Assistant connection at all - that
lower layer (reconnect, backoff, the "connected"/resync marker itself) is
covered by services/home-assistant-adapter/tests/test_ha_client_subscribe_events.py
and test_adapter_mock.py.
"""

from collections.abc import AsyncIterator, Callable

from app.domain.capabilities import CapabilityType, OnOffState
from app.domain.device import DomainDevice
from app.events import DeviceStateEvent, InMemoryEventBus
from app.services.ha_event_ingestion import HomeAssistantEventIngestionService


class _FakeAdapter:
    """Stands in for TranslatingHomeAssistantAdapter: a scripted sequence
    of subscribe_events() items, plus a `devices` dict that list_devices()
    (called during every "resync" item) reads from.

    Queued mutation callables let a test change `devices` *between* two
    already-queued items rather than before `run()` starts at all - the
    ingestion service consumes subscribe_events() one item at a time via
    `async for`, only pulling the next item once it's fully done
    processing the current one, so a mutation queued between two resyncs
    only actually happens once the first resync's own list_devices() call
    has already completed. Mutating `devices` synchronously before
    calling run() at all (as an earlier version of this fixture did) would
    make every resync see the same already-mutated state - it wouldn't
    exercise "diffed against what was last known" at all."""

    def __init__(self) -> None:
        self.devices: dict[str, DomainDevice] = {}
        self._queued_events: list[dict | Callable[[], None]] = []

    def seed(self, device: DomainDevice) -> None:
        self.devices[device.id] = device

    def queue_resync(self) -> None:
        self._queued_events.append({"kind": "resync"})

    def queue_device_changed(self, device: DomainDevice) -> None:
        self._queued_events.append({"kind": "device_changed", "device": device})

    def queue_mutation(self, mutate: Callable[[], None]) -> None:
        self._queued_events.append(mutate)

    async def list_devices(self) -> list[DomainDevice]:
        return list(self.devices.values())

    async def subscribe_events(self) -> AsyncIterator[dict]:
        for item in self._queued_events:
            if callable(item):
                item()
            else:
                yield item


def _light(device_id: str, *, is_on: bool) -> DomainDevice:
    return DomainDevice(
        id=device_id, name="Lamp", device_type="light", capabilities={CapabilityType.ON_OFF: OnOffState(is_on=is_on)}
    )


async def _run_queued(service: HomeAssistantEventIngestionService, adapter: _FakeAdapter) -> None:
    """`run()` iterates forever in production; tests only ever queue a
    finite, already-known sequence of items, so the loop ends naturally
    once `subscribe_events()`'s fixed list is exhausted."""
    await service.run()


# --- initial snapshot --------------------------------------------------------


async def test_initial_resync_publishes_state_changed_for_every_known_device():
    adapter = _FakeAdapter()
    adapter.seed(_light("light-1", is_on=True))
    adapter.queue_resync()
    bus = InMemoryEventBus()
    service = HomeAssistantEventIngestionService(adapter, bus)

    await _run_queued(service, adapter)

    events = await bus.recent(limit=10)
    assert len(events) == 1
    assert events[0].type == "device.state_changed"
    assert events[0].payload["deviceId"] == "light-1"
    assert events[0].payload["capabilities"]["on_off"]["is_on"] is True


async def test_initial_resync_with_no_devices_publishes_nothing():
    adapter = _FakeAdapter()
    adapter.queue_resync()
    bus = InMemoryEventBus()
    service = HomeAssistantEventIngestionService(adapter, bus)

    await _run_queued(service, adapter)

    assert await bus.recent(limit=10) == []


# --- incremental updates ------------------------------------------------------


async def test_device_changed_event_publishes_state_changed():
    adapter = _FakeAdapter()
    adapter.seed(_light("light-1", is_on=False))
    adapter.queue_resync()
    adapter.queue_device_changed(_light("light-1", is_on=True))
    bus = InMemoryEventBus()
    service = HomeAssistantEventIngestionService(adapter, bus)

    await _run_queued(service, adapter)

    events = await bus.recent(limit=10)
    assert len(events) == 2  # initial resync snapshot + the incremental change
    assert events[0].payload["capabilities"]["on_off"]["is_on"] is True  # newest first


async def test_device_changed_event_with_no_actual_state_difference_publishes_nothing():
    """An incremental update that doesn't actually change anything (HA can
    send redundant state_changed events, e.g. an attribute-only update
    that maps to the same SystemONE capability value) must not spam a
    duplicate event."""
    adapter = _FakeAdapter()
    adapter.seed(_light("light-1", is_on=True))
    adapter.queue_resync()
    adapter.queue_device_changed(_light("light-1", is_on=True))  # identical state
    bus = InMemoryEventBus()
    service = HomeAssistantEventIngestionService(adapter, bus)

    await _run_queued(service, adapter)

    events = await bus.recent(limit=10)
    assert len(events) == 1  # only the initial resync snapshot


# --- reconnect / resync: the core S1V2-02-020 guarantee ----------------------


async def test_resync_after_reconnect_catches_a_change_missed_while_disconnected():
    """The scenario the whole task exists for: a state change happens
    while the WebSocket is down, so no `device_changed` item is ever
    delivered for it - the connection then recovers, the adapter yields a
    fresh "resync" marker, and list_devices() (now returning the *current*
    state) must be diffed against what was last known so the missed
    change still reaches the event bus exactly once."""
    adapter = _FakeAdapter()
    adapter.seed(_light("light-1", is_on=False))
    adapter.queue_resync()  # initial snapshot: light-1 off

    # Connection drops here - HA changes light-1 to on while nobody is
    # listening, then the connection recovers and re-subscribes, which
    # the adapter always surfaces as another "resync" item. Queued as a
    # mutation (not applied yet) so it only actually happens once the
    # first resync's own list_devices() call has already completed.
    adapter.queue_mutation(lambda: adapter.devices.__setitem__("light-1", _light("light-1", is_on=True)))
    adapter.queue_resync()

    bus = InMemoryEventBus()
    service = HomeAssistantEventIngestionService(adapter, bus)

    await _run_queued(service, adapter)

    events = await bus.recent(limit=10)
    assert len(events) == 2  # initial snapshot (off) + resync-recovered change (on)
    assert events[0].payload["capabilities"]["on_off"]["is_on"] is True  # newest first: the recovered change
    assert events[1].payload["capabilities"]["on_off"]["is_on"] is False


async def test_resync_publishes_nothing_for_devices_unchanged_since_last_known_state():
    """A reconnect where nothing actually changed while disconnected must
    not manufacture a spurious duplicate event for every device."""
    adapter = _FakeAdapter()
    adapter.seed(_light("light-1", is_on=True))
    adapter.queue_resync()
    adapter.queue_resync()  # reconnect, but light-1's state is identical
    bus = InMemoryEventBus()
    service = HomeAssistantEventIngestionService(adapter, bus)

    await _run_queued(service, adapter)

    events = await bus.recent(limit=10)
    assert len(events) == 1  # only the first resync's snapshot


async def test_resync_publishes_device_removed_for_a_device_no_longer_present():
    adapter = _FakeAdapter()
    adapter.seed(_light("light-1", is_on=True))
    adapter.queue_resync()
    adapter.queue_mutation(lambda: adapter.devices.pop("light-1"))  # removed from HA while disconnected
    adapter.queue_resync()
    bus = InMemoryEventBus()
    service = HomeAssistantEventIngestionService(adapter, bus)

    await _run_queued(service, adapter)

    events = await bus.recent(limit=10)
    assert events[0].type == "device.removed"
    assert events[0].payload == {"deviceId": "light-1"}
