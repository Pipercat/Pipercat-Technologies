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

    async def list_entity_registry(self) -> list[dict[str, Any]]:
        """Raw HA entity-registry rows (S1V2-02-017: "Räume ... stabil
        zuordnen") - each entity's own `area_id` if explicitly set, else
        `None`, plus the `device_id` of its parent HA device (which may
        itself carry the area assignment - see list_device_registry())."""
        result = await self._client.send_command("config/entity_registry/list")
        return [
            {"entityId": row["entity_id"], "areaId": row.get("area_id"), "deviceId": row.get("device_id")}
            for row in result
        ]

    async def list_device_registry(self) -> list[dict[str, Any]]:
        """Raw HA device-registry rows - an entity with no area of its own
        inherits its parent device's area (standard Home Assistant
        behaviour: most integrations set the area on the device, not each
        individual entity)."""
        result = await self._client.send_command("config/device_registry/list")
        return [{"id": row["id"], "areaId": row.get("area_id")} for row in result]

    async def zha_permit_join(self, *, duration_seconds: int = 60) -> None:
        """Starts ZHA's Zigbee pairing window (S1V2-02-021 follow-up,
        `S1V2-02-022`: "Pairing über SystemONE anstoßen"). `zha.permit` is
        a real, documented Home Assistant service (`domain="zha"`,
        `service="permit"`, field `duration` - see the `zha` integration's
        own `services.yaml` in home-assistant/core) - not a bespoke
        SystemONE mechanism, so it needs no new low-level protocol code
        beyond the already-existing `call_service()`."""
        await self._client.call_service("zha", "permit", {"duration": duration_seconds})

    async def zha_remove_device(self, *, ieee: str) -> None:
        """`zha.remove` (real HA service, field `ieee` - same source as
        `zha_permit_join()`) unpairs a Zigbee device from the coordinator."""
        await self._client.call_service("zha", "remove", {"ieee": ieee})

    async def zha_list_devices(self) -> list[dict[str, Any]]:
        """Raw `zha/devices` WebSocket command passthrough (real HA
        command - see the `zha` integration's `websocket_api.py::
        websocket_get_devices`) - each returned dict is HA's own
        `ZHADeviceInfo` shape and includes at least an `ieee` field.
        Deliberately a raw passthrough rather than a further-normalized
        SystemONE type: `ZHADeviceInfo`'s exact nested field layout ships
        in the separate `zha` PyPI package, not `home-assistant/core`
        itself, and this codebase has no real Zigbee coordinator to
        validate a parser against yet - see
        docs/architecture/zigbee-integration.md's "Bekannte Grenzen"."""
        return await self._client.send_command("zha/devices")

    async def resolve_ha_device_id(self, device_id: str) -> str | None:
        """Maps a SystemONE `device_id` to Home Assistant's own internal
        device-registry id (S1V2-02-023) - Matter's commissioning-window/
        remove-fabric commands identify a node by HA `device_id`, not by
        `entity_id` (unlike Zigbee's `ieee`, see zigbee-integration.md).
        Reuses `list_entity_registry()` (S1V2-02-017) rather than
        introducing a second correlation mechanism - `None` if the device
        was never discovered via `list_devices()` (no entity_id cached
        yet) or has no HA device-registry entry."""
        entity_id = self._entity_id_by_device_id.get(device_id)
        if entity_id is None:
            return None
        for row in await self.list_entity_registry():
            if row["entityId"] == entity_id:
                return row["deviceId"]
        return None

    async def matter_commission_with_code(self, *, code: str, network_only: bool = True) -> None:
        """`matter/commission` (real HA WebSocket command, fields `code`/
        `network_only` - see the `matter` integration's `api.py::
        websocket_commission` in home-assistant/core) - pairs a Matter
        device via its QR/manual pairing code."""
        await self._client.send_command("matter/commission", code=code, network_only=network_only)

    async def matter_commission_on_network(self, *, pin: int, ip_addr: str | None = None) -> None:
        """`matter/commission_on_network` (real HA command, fields `pin`/
        optional `ip_addr` - same source) - pairs a Matter device that is
        already reachable on the local network via its numeric PIN."""
        extra: dict[str, Any] = {"pin": pin}
        if ip_addr is not None:
            extra["ip_addr"] = ip_addr
        await self._client.send_command("matter/commission_on_network", **extra)

    async def matter_remove_fabric(self, *, ha_device_id: str, fabric_index: int) -> None:
        """`matter/remove_matter_fabric` (real HA command, fields
        `device_id`/`fabric_index` - same source) - un-pairs a Matter
        device from this Home Assistant instance's fabric. `ha_device_id`
        is HA's own device-registry id (see `resolve_ha_device_id()`),
        not a SystemONE `device_id` or `entity_id`."""
        await self._client.send_command("matter/remove_matter_fabric", device_id=ha_device_id, fabric_index=fabric_index)

    async def matter_node_diagnostics(self, *, ha_device_id: str) -> dict[str, Any]:
        """Raw `matter/node_diagnostics` passthrough (real HA command -
        same source) - needed to discover which `fabric_index` to pass to
        `matter_remove_fabric()`. Deliberately unprocessed: its exact
        nested shape comes from the separate `python-matter-server`
        client, not `home-assistant/core` itself, and this codebase has no
        real Matter controller to validate a parser against yet - see
        docs/architecture/matter-integration.md's "Bekannte Grenzen"."""
        return await self._client.send_command("matter/node_diagnostics", device_id=ha_device_id)

    async def subscribe_events(self) -> AsyncIterator[dict[str, Any]]:
        """Yields normalized items for every live Home Assistant
        state_changed event, reconnecting transparently on connection loss
        (see HomeAssistantClient):

        - `{"kind": "resync"}` every time the underlying subscription is
          (re)established - including the very first one. Signals "treat
          this as a fresh start: fetch a full snapshot via list_devices()
          and reconcile" (S1V2-02-020) rather than "wait for the next
          incremental update" - the only way to recover state changes that
          happened while disconnected, since Home Assistant's event stream
          itself has no concept of "catch me up from timestamp X".
        - `{"kind": "device_changed", "deviceId", "entityId", "device"}`
          for each incremental state_changed event - unchanged shape from
          before S1V2-02-020, plus the new "kind" key.
        """
        async for item in self._client.subscribe_events("state_changed"):
            if item["kind"] == "connected":
                yield {"kind": "resync"}
                continue

            new_state = item["event"].get("data", {}).get("new_state")
            if new_state is None:  # entity removed - nothing to report
                continue
            device = state_to_device_dict(new_state)
            self._entity_id_by_device_id[device["id"]] = new_state["entity_id"]
            yield {"kind": "device_changed", "deviceId": device["id"], "entityId": new_state["entity_id"], "device": device}
