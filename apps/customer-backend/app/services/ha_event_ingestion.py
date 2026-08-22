"""Consumes the live Home Assistant event stream and republishes it as
SystemONE `DeviceStateEvent`s (S1V2-02-020).

`DeviceService`/`AutomationEngine` are already always-live: every
`list_devices()`/`get_device()` call re-fetches current state from the
adapter, nothing is cached (see `app/domain/service.py`). So "konsistenter
SystemONE-Zustand" after a reconnect is not a database-repair problem -
there is no persisted device-state table to repair (see
`docs/architecture/ha-event-sync.md`'s "Bekannte Grenzen"). It is an
event-completeness problem: `AutomationEngine.on_device_event()` and any
other event-driven consumer must eventually see one event per state
change, even for changes that happened while the WebSocket connection was
down and could never have arrived as an incremental
`state_changed` message.

This service tracks the last-known state of every device *only* to detect
what changed - never as a cache that anything else reads. Whenever
`TranslatingHomeAssistantAdapter.subscribe_events()` yields a `resync`
item (every initial connect and every reconnect after a drop - see that
module and `home_assistant_adapter.ha_client`), it re-fetches the full
device list and diffs it against what was last known, publishing one
`device.state_changed` event per device whose capabilities differ - which
transparently covers both "the very first snapshot" and "everything that
changed while disconnected" with the same code path.
"""

import logging

from app.domain.device import DomainDevice
from app.events import DeviceStateEvent, EventBus
from app.services.ha_device_adapter import TranslatingHomeAssistantAdapter

logger = logging.getLogger("systemone.customer_backend.ha_event_ingestion")


class HomeAssistantEventIngestionService:
    def __init__(self, adapter: TranslatingHomeAssistantAdapter, event_bus: EventBus) -> None:
        self._adapter = adapter
        self._event_bus = event_bus
        self._known_devices: dict[str, DomainDevice] = {}

    async def run(self) -> None:
        """Runs forever - `subscribe_events()` only ends if the adapter's
        own generator ends, which it never does under normal operation
        (the client-level reconnect loop is itself a `while True`)."""
        async for item in self._adapter.subscribe_events():
            if item["kind"] == "resync":
                await self._resync()
            else:
                await self._apply_device_changed(item["device"])

    async def _resync(self) -> None:
        devices = await self._adapter.list_devices()
        fresh = {device.id: device for device in devices}

        changed = [device for device_id, device in fresh.items() if self._known_devices.get(device_id) != device]
        removed_ids = [device_id for device_id in self._known_devices if device_id not in fresh]

        self._known_devices = fresh
        for device in changed:
            await self._publish_state_changed(device)
        for device_id in removed_ids:
            await self._event_bus.publish(
                DeviceStateEvent(type="device.removed", payload={"deviceId": device_id}),
            )
        logger.info(
            "ha_resync_completed device_count=%d changed=%d removed=%d",
            len(fresh),
            len(changed),
            len(removed_ids),
        )

    async def _apply_device_changed(self, device: DomainDevice) -> None:
        previous = self._known_devices.get(device.id)
        self._known_devices[device.id] = device
        if previous != device:
            await self._publish_state_changed(device)

    async def _publish_state_changed(self, device: DomainDevice) -> None:
        await self._event_bus.publish(
            DeviceStateEvent(
                type="device.state_changed",
                payload={
                    "deviceId": device.id,
                    "capabilities": {
                        capability_type.value: state.model_dump(mode="json")
                        for capability_type, state in device.capabilities.items()
                    },
                },
            )
        )
