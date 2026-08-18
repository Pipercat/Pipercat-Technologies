"""HomeAssistantClient.subscribe_events() reconnect/resync behaviour
(S1V2-02-020 DoD: "HA-Neustart und Netzunterbrechung führen nach
Wiederverbindung zu konsistentem SystemONE-Zustand").

Exercises the reconnect loop directly by faking `_connect_and_authenticate`
- the WebSocket auth handshake itself is already S1V2-02-016's concern
  (covered by test_real_ha_integration.py against a real HA instance); this
  file isolates the reconnect/backoff/resync-marker state machine so it can
  be tested without a live server or a real dropped TCP connection.
"""

import json

import pytest
from websockets.exceptions import ConnectionClosed

from home_assistant_adapter.ha_client import HomeAssistantClient


class _FakeWebSocket:
    """One simulated WebSocket connection's worth of behaviour after the
    auth handshake: an optional subscribe-ack rejection, a fixed sequence
    of state_changed events, and an optional error raised once the events
    are exhausted (simulating a mid-stream drop)."""

    def __init__(self, events: list[dict], *, subscribe_ack_ok: bool = True, drop_with: Exception | None = None) -> None:
        self._subscribe_ack_ok = subscribe_ack_ok
        self._events = events
        self._drop_with = drop_with
        self.closed = False

    async def send(self, _raw: str) -> None:
        pass  # the subscribe_events request itself - nothing to validate here

    async def recv(self) -> str:
        return json.dumps({"success": self._subscribe_ack_ok, "error": None if self._subscribe_ack_ok else "rejected"})

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for event in self._events:
            yield json.dumps({"type": "event", "event": event})
        if self._drop_with is not None:
            raise self._drop_with


def _client_with_fake_connections(connections: list) -> HomeAssistantClient:
    """`connections` is a list of `_FakeWebSocket` instances (yielded one
    per successful (re)connect) and/or `Exception` instances (raised by
    `_connect_and_authenticate` itself, simulating a connect-time failure
    before any WebSocket exists)."""
    client = HomeAssistantClient(base_url="http://unused.invalid", access_token="unused")
    remaining = list(connections)

    async def fake_connect_and_authenticate():
        item = remaining.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    client._connect_and_authenticate = fake_connect_and_authenticate  # replacing the handshake is the whole point
    return client


def _event(entity_id: str, state: str) -> dict:
    return {"data": {"entity_id": entity_id, "new_state": {"entity_id": entity_id, "state": state, "attributes": {}}}}


async def _take(aiter, count: int) -> list[dict]:
    items = []
    async for item in aiter:
        items.append(item)
        if len(items) == count:
            break
    return items


async def test_yields_connected_marker_before_the_first_event():
    ws = _FakeWebSocket([_event("light.a", "on")])
    client = _client_with_fake_connections([ws])

    items = await _take(client.subscribe_events(), count=2)

    assert items[0] == {"kind": "connected"}
    assert items[1]["kind"] == "event"
    assert items[1]["event"]["data"]["entity_id"] == "light.a"


async def test_reconnect_after_a_dropped_connection_yields_a_fresh_resync_marker():
    """The core S1V2-02-020 guarantee at the client layer: a connection
    drop is never silently resumed as "just keep listening" - the next
    successful (re)subscription always announces itself with another
    "connected" marker, so callers above this layer know to reconcile
    against a full snapshot rather than trust they saw every change."""
    ws1 = _FakeWebSocket([_event("light.a", "on")], drop_with=ConnectionClosed(None, None))
    ws2 = _FakeWebSocket([_event("light.b", "off")])
    client = _client_with_fake_connections([ws1, ws2])

    # ws1: connected, event(light.a) - then drop_with fires when exhausted;
    # the reconnect loop opens ws2, which yields its own connected marker
    # before light.b's event.
    items = await _take(client.subscribe_events(), count=4)

    assert [item["kind"] for item in items] == ["connected", "event", "connected", "event"]
    assert items[1]["event"]["data"]["entity_id"] == "light.a"
    assert items[3]["event"]["data"]["entity_id"] == "light.b"
    assert ws1.closed


async def test_rejected_subscription_is_retried_without_ever_yielding_connected():
    """A rejected subscribe_events ack (HA-side error, not a network drop)
    must be exactly as retryable as a dropped connection - the previous
    behaviour let this exception escape the generator entirely, silently
    ending the live-event stream for good."""
    ws1 = _FakeWebSocket([], subscribe_ack_ok=False)
    ws2 = _FakeWebSocket([_event("light.a", "on")])
    client = _client_with_fake_connections([ws1, ws2])

    items = await _take(client.subscribe_events(), count=2)

    assert items[0] == {"kind": "connected"}  # only ever from ws2 - ws1's ack was rejected first
    assert items[1]["event"]["data"]["entity_id"] == "light.a"


async def test_connect_time_failure_is_retried_with_backoff(monkeypatch):
    from home_assistant_adapter import ha_client as ha_client_module

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(ha_client_module.asyncio, "sleep", fake_sleep)

    from home_assistant_adapter.errors import HomeAssistantConnectionError

    ws = _FakeWebSocket([_event("light.a", "on")])
    client = _client_with_fake_connections([HomeAssistantConnectionError("down"), ws])

    items = await _take(client.subscribe_events(), count=2)

    assert sleep_calls == [ha_client_module.DEFAULT_RECONNECT_BACKOFF_SECONDS]
    assert items[0] == {"kind": "connected"}
