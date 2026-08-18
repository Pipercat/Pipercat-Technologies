"""HomeAssistantAdapter (S1V2-02-016): SystemONE's single production
smart-home integration boundary (ADR-0002). No other code path may talk
to Home Assistant, Zigbee, Matter, Shelly or Hue directly.

Structurally satisfies `apps/customer-backend/app/domain/adapter_port.py`
::DeviceAdapterPort (`list_devices`/`apply_command`) - the same method
names, so it can replace `SimulationDeviceAdapter` in `DeviceService`
without any domain/service code changes, per
docs/architecture/domain-device-model.md. Also exposes `list_areas` and
`subscribe_events`, covering the remaining "Discovery, Zustände,
Services/Aktionen, Areas und Live-Events" scope this task's Notion
"Umsetzung" names - neither has a domain-layer consumer yet (that lands
with the area/room-mapping and event-ingestion follow-up tasks), but the
adapter itself is ready.

Connection lifecycle (auth, reconnect, timeout) is fully encapsulated in
`HomeAssistantClient` (ha_client.py) - this class only translates between
that client's HA-shaped data and SystemONE-shaped device dicts (mapping.py).
"""

from collections.abc import AsyncIterator
from typing import Any

from .errors import DeviceNotFoundError
from .ha_client import HomeAssistantClient
from .mapping import command_to_service_call, entity_domain, state_to_device_dict


class HomeAssistantAdapter:
    def __init__(self, base_url: str, access_token: str, *, timeout_seconds: float = 10.0) -> None:
        self._client = HomeAssistantClient(base_url, access_token, timeout_seconds=timeout_seconds)
        # Populated by list_devices() - apply_command() needs it to turn a
        # SystemONE device id back into the HA entity_id that produced it,
        # since the id itself is a one-way UUID5 derivation (see mapping.py).
        self._entity_id_by_device_id: dict[str, str] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def list_devices(self) -> list[dict[str, Any]]:
        states = await self._client.get_states()
        devices = [state_to_device_dict(state) for state in states]
        self._entity_id_by_device_id = {
            device["id"]: state["entity_id"] for device, state in zip(devices, states, strict=True)
        }
        return devices

    async def apply_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        entity_id = self._entity_id_by_device_id.get(device_id)
        if entity_id is None:
            raise DeviceNotFoundError(device_id)

        domain = entity_domain(entity_id)
        service_domain, service, extra = command_to_service_call(domain, command)
        await self._client.call_service(service_domain, service, {"entity_id": entity_id, **extra})

        # Re-read the entity's new state so callers get the authoritative
        # post-command value rather than optimistically echoing the
        # request back (a service call can be clamped/rejected by HA).
        states = await self._client.get_states()
        for state in states:
            if state["entity_id"] == entity_id:
                return state_to_device_dict(state)["capabilities"].get(command.get("type"), {})
        raise DeviceNotFoundError(device_id)

    async def list_areas(self) -> list[dict[str, Any]]:
        result = await self._client.send_command("config/area_registry/list")
        return [{"id": area["area_id"], "name": area["name"]} for area in result]

    async def subscribe_events(self) -> AsyncIterator[dict[str, Any]]:
        """Yields normalized {"deviceId", "entityId", "state"} dicts for
        every live Home Assistant state_changed event, reconnecting
        transparently on connection loss (see HomeAssistantClient)."""
        async for event in self._client.subscribe_events("state_changed"):
            new_state = event.get("data", {}).get("new_state")
            if new_state is None:  # entity removed - nothing to report
                continue
            device = state_to_device_dict(new_state)
            self._entity_id_by_device_id[device["id"]] = new_state["entity_id"]
            yield {"deviceId": device["id"], "entityId": new_state["entity_id"], "device": device}
