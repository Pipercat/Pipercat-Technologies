"""Orchestrates Zigbee pairing/removal through Home Assistant's ZHA
integration (S1V2-02-022).

"Kein direkter Zigbee-Stack in Flutter": SystemONE's own API is the only
thing the customer app ever talks to; this service is the one place
`apps/customer-backend` triggers ZHA's pairing window or removes a
device - matching ADR-0002's single-integration-boundary rule the same
way `DeviceCommandService` (S1V2-02-019) and `HomeAssistantImportService`
(S1V2-02-017) already do for device commands and area/device import.

"Geräte erscheinen nach Pairing über reguläres Device Model": deliberately
no new device representation here - a newly joined Zigbee device is just
another Home Assistant entity, already fully handled by the existing
`list_devices()`/mapping pipeline (S1V2-02-016/-018) the moment ZHA
creates it. `discover_new_devices()` only *diffs* against a snapshot to
report which already-normal `DomainDevice`s are new, it does not invent a
parallel Zigbee-specific device type.

"Fortschritt ... darstellen" is poll-based (`discover_new_devices()`
against a snapshot taken by `start_pairing()`), not a live event stream -
matching this codebase's established live-query philosophy
(`DeviceService` never caches, see app/domain/service.py) rather than
building new streaming machinery whose exact Home Assistant event shape
cannot be verified without a real Zigbee coordinator (see
docs/architecture/zigbee-integration.md's "Bekannte Grenzen").
"""

from app.audit import AuditRecorder
from app.authorization import Actor, require_permission
from app.domain.device import DomainDevice
from app.services.ha_device_adapter import TranslatingHomeAssistantAdapter


class ZigbeePairingService:
    def __init__(self, adapter: TranslatingHomeAssistantAdapter, audit: AuditRecorder) -> None:
        self._adapter = adapter
        self._audit = audit

    async def start_pairing(self, actor: Actor, *, duration_seconds: int = 60) -> set[str]:
        """Returns the snapshot of device ids known *before* pairing
        starts - pass it to `discover_new_devices()` later to see what
        joined during the pairing window."""
        require_permission(actor, "devices:manage")
        known_device_ids = {device.id for device in await self._adapter.list_devices()}

        try:
            await self._adapter.start_zigbee_pairing(duration_seconds=duration_seconds)
        except Exception:
            self._audit.record(
                actor=actor,
                action="zigbee.pairing_failed",
                target_type="zigbee_gateway",
                target_id="zha",
                outcome="failure",
                metadata={"durationSeconds": duration_seconds},
            )
            raise

        self._audit.record(
            actor=actor,
            action="zigbee.pairing_started",
            target_type="zigbee_gateway",
            target_id="zha",
            outcome="success",
            metadata={"durationSeconds": duration_seconds},
        )
        return known_device_ids

    async def discover_new_devices(self, *, known_before: set[str]) -> list[DomainDevice]:
        devices = await self._adapter.list_devices()
        return [device for device in devices if device.id not in known_before]

    async def remove_device(self, actor: Actor, *, ieee: str) -> None:
        require_permission(actor, "devices:manage")

        try:
            await self._adapter.remove_zigbee_device(ieee=ieee)
        except Exception:
            self._audit.record(
                actor=actor,
                action="zigbee.device_remove_failed",
                target_type="zigbee_device",
                target_id=ieee,
                outcome="failure",
                metadata={},
            )
            raise

        self._audit.record(
            actor=actor,
            action="zigbee.device_removed",
            target_type="zigbee_device",
            target_id=ieee,
            outcome="success",
            metadata={},
        )
