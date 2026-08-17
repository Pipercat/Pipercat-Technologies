"""MQTT-backed EventBus (S1V2-02-004). See docs/architecture/mqtt-eventbus.md
for the full design rationale (topic convention, QoS/retain, reconnect,
duplicate-delivery handling).

No caller outside this module may import aiomqtt directly - everything
goes through EventBus (app/events.py), same boundary discipline as
services/home-assistant-adapter.
"""

import asyncio
import contextlib
import json
import logging
from collections import OrderedDict, deque

import aiomqtt

from .events import DeviceStateEvent, EventBus, EventHandler

logger = logging.getLogger("systemone.customer_backend.mqtt")

TOPIC_PREFIX = "systemone/v1/events"
_MAX_RETAINED = 500
_MAX_OUTBOX = 200
_MAX_SEEN_IDS = 1000
_RECONNECT_DELAY_SECONDS = 2


def topic_for(event_type: str) -> str:
    # No device/user identifiers in the topic itself - only the (already
    # PII-free) event type. Identifying data, if any, lives in the payload.
    return f"{TOPIC_PREFIX}/{event_type}"


class MqttEventBus(EventBus):
    def __init__(self, hostname: str, port: int = 1883, reconnect_delay: float = _RECONNECT_DELAY_SECONDS) -> None:
        self._hostname = hostname
        self._port = port
        self._reconnect_delay = reconnect_delay
        self._events: deque[DeviceStateEvent] = deque(maxlen=_MAX_RETAINED)
        self._handlers: list[EventHandler] = []
        self._outbox: deque[DeviceStateEvent] = deque(maxlen=_MAX_OUTBOX)
        self._seen_ids: OrderedDict[str, None] = OrderedDict()
        self._client: aiomqtt.Client | None = None
        self.connected = asyncio.Event()
        self._run_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._run_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._run_task is not None:
            self._run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._run_task
            self._run_task = None

    async def _run(self) -> None:
        while True:
            try:
                async with aiomqtt.Client(hostname=self._hostname, port=self._port) as client:
                    self._client = client
                    # Subscribe *before* flushing the outbox or signalling
                    # "connected": publishing before the subscription is
                    # active means the broker has nowhere to route our own
                    # messages back to, and a caller could publish() into a
                    # window where we're "connected" but not yet listening.
                    await client.subscribe(f"{TOPIC_PREFIX}/#", qos=1)
                    self.connected.set()
                    await self._flush_outbox()
                    async for message in client.messages:
                        await self._handle_message(message.topic.value, message.payload)
            except aiomqtt.MqttError:
                logger.warning("mqtt_disconnected_retrying")
                self.connected.clear()
                self._client = None
                await asyncio.sleep(self._reconnect_delay)

    async def _handle_message(self, topic: str, raw_payload: bytes | bytearray | str) -> None:
        try:
            data = json.loads(raw_payload)
            event = DeviceStateEvent.model_validate(data)
        except Exception:
            logger.warning("mqtt_invalid_payload topic=%s", topic)
            return

        if event.id in self._seen_ids:
            logger.info("mqtt_duplicate_event_dropped event_id=%s", event.id)
            return
        self._seen_ids[event.id] = None
        while len(self._seen_ids) > _MAX_SEEN_IDS:
            self._seen_ids.popitem(last=False)

        self._events.append(event)
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception:
                # A broken subscriber must not take down the reconnect loop
                # or block delivery to other subscribers.
                logger.exception("mqtt_handler_failed event_id=%s", event.id)

    async def _flush_outbox(self) -> None:
        while self._outbox:
            event = self._outbox.popleft()
            await self._publish_now(event)

    async def _publish_now(self, event: DeviceStateEvent) -> None:
        assert self._client is not None
        payload = event.model_dump_json().encode("utf-8")
        # QoS 1 (at-least-once) + retain=False: see module docstring.
        await self._client.publish(topic_for(event.type), payload=payload, qos=1, retain=False)

    async def publish(self, event: DeviceStateEvent) -> None:
        if self._client is None:
            self._outbox.append(event)
            logger.warning("mqtt_offline_queued event_type=%s", event.type)
            return
        try:
            await self._publish_now(event)
        except aiomqtt.MqttError:
            self._outbox.append(event)
            logger.warning("mqtt_publish_failed_queued event_type=%s", event.type)

    async def recent(self, limit: int = 50) -> list[DeviceStateEvent]:
        return list(reversed(self._events))[:limit]

    async def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    @property
    def outbox_size(self) -> int:
        return len(self._outbox)
