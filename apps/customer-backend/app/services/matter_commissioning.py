"""Orchestrates Matter commissioning/removal through Home Assistant's
`matter` integration (S1V2-02-023).

Mirrors `app.services.zigbee_pairing.ZigbeePairingService`'s shape - same
permission/audit/snapshot-diff pattern, same "kein direkter [Protokoll]-
Stack in Flutter" and "Geräte erscheinen über reguläres Device Model"
reasoning (see that module's docstring). Deliberately a separate service
rather than a shared abstraction over both integrations: the two DoDs
overlap in shape but not in mechanism (Matter commissioning takes a
pairing code or PIN, not a permit-join duration; Matter removal needs a
fabric_index looked up from the device, not a caller-supplied address) -
duplicating the small amount of shared logic (start/diff) keeps each
integration's real differences visible instead of hiding them behind a
premature shared base class.

"Nicht unterstützte Fabric-/Cloud-Sonderfälle klar melden": no bespoke
error taxonomy is invented here - a rejected commissioning attempt (wrong
code, a device requiring cloud/vendor-app setup Home Assistant's `matter`
integration doesn't support, etc.) already reaches the caller as
`TransientDeviceError` with Home Assistant's own error text preserved
(see `HomeAssistantClient.send_command()`), which is a real, sufficient
signal without guessing at Matter-specific failure subtypes that would
need a live Matter controller to enumerate correctly.
"""

from app.audit import AuditRecorder
from app.authorization import Actor, require_permission
from app.domain.device import DomainDevice
from app.services.ha_device_adapter import TranslatingHomeAssistantAdapter


class MatterCommissioningService:
    def __init__(self, adapter: TranslatingHomeAssistantAdapter, audit: AuditRecorder) -> None:
        self._adapter = adapter
        self._audit = audit

    async def start_commissioning_with_code(self, actor: Actor, *, code: str, network_only: bool = True) -> set[str]:
        """Returns the snapshot of device ids known *before* commissioning
        starts - pass it to `discover_new_devices()` later."""
        require_permission(actor, "devices:manage")
        known_device_ids = {device.id for device in await self._adapter.list_devices()}

        try:
            await self._adapter.start_matter_commissioning_with_code(code=code, network_only=network_only)
        except Exception:
            self._audit.record(
                actor=actor,
                action="matter.commissioning_failed",
                target_type="matter_gateway",
                target_id="matter",
                outcome="failure",
                metadata={"method": "code"},
            )
            raise

        self._audit.record(
            actor=actor,
            action="matter.commissioning_started",
            target_type="matter_gateway",
            target_id="matter",
            outcome="success",
            metadata={"method": "code"},
        )
        return known_device_ids

    async def start_commissioning_on_network(self, actor: Actor, *, pin: int, ip_addr: str | None = None) -> set[str]:
        require_permission(actor, "devices:manage")
        known_device_ids = {device.id for device in await self._adapter.list_devices()}

        try:
            await self._adapter.start_matter_commissioning_on_network(pin=pin, ip_addr=ip_addr)
        except Exception:
            self._audit.record(
                actor=actor,
                action="matter.commissioning_failed",
                target_type="matter_gateway",
                target_id="matter",
                outcome="failure",
                metadata={"method": "network"},
            )
            raise

        self._audit.record(
            actor=actor,
            action="matter.commissioning_started",
            target_type="matter_gateway",
            target_id="matter",
            outcome="success",
            metadata={"method": "network"},
        )
        return known_device_ids

    async def discover_new_devices(self, *, known_before: set[str]) -> list[DomainDevice]:
        devices = await self._adapter.list_devices()
        return [device for device in devices if device.id not in known_before]

    async def remove_device(self, actor: Actor, *, device_id: str, fabric_index: int) -> None:
        require_permission(actor, "devices:manage")

        try:
            await self._adapter.remove_matter_device(device_id=device_id, fabric_index=fabric_index)
        except Exception:
            self._audit.record(
                actor=actor,
                action="matter.device_remove_failed",
                target_type="matter_device",
                target_id=device_id,
                outcome="failure",
                metadata={"fabricIndex": fabric_index},
            )
            raise

        self._audit.record(
            actor=actor,
            action="matter.device_removed",
            target_type="matter_device",
            target_id=device_id,
            outcome="success",
            metadata={"fabricIndex": fabric_index},
        )
