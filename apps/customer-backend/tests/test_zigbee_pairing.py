"""S1V2-02-022 Definition of Done (software half - see
docs/architecture/zigbee-integration.md's "Bekannte Grenzen" for why the
"mindestens ein reales ... Gerät" hardware half cannot be verified in
this environment): permission-gated pairing/removal, audit trail on
both success and failure, "Geräte erscheinen über reguläres Device
Model" (discover_new_devices() returns plain DomainDevice, nothing
Zigbee-specific).

Uses a bare double for TranslatingHomeAssistantAdapter - this service
only ever calls list_devices()/start_zigbee_pairing()/
remove_zigbee_device() on it (structural typing), so a double satisfying
that surface is a faithful substitute without a real Home Assistant or
Zigbee coordinator."""

import pytest

from app.audit import InMemoryAuditRecorder
from app.authorization import AuthorizationError
from app.domain.capabilities import CapabilityType, OnOffState
from app.domain.device import DomainDevice
from app.services.zigbee_pairing import ZigbeePairingService
from tests.fakes import make_actor


class _FakeAdapter:
    def __init__(self) -> None:
        self.devices: list[DomainDevice] = []
        self.start_pairing_calls: list[int] = []
        self.remove_calls: list[str] = []
        self.start_pairing_error: Exception | None = None
        self.remove_error: Exception | None = None

    async def list_devices(self) -> list[DomainDevice]:
        return list(self.devices)

    async def start_zigbee_pairing(self, *, duration_seconds: int = 60) -> None:
        self.start_pairing_calls.append(duration_seconds)
        if self.start_pairing_error is not None:
            raise self.start_pairing_error

    async def remove_zigbee_device(self, *, ieee: str) -> None:
        self.remove_calls.append(ieee)
        if self.remove_error is not None:
            raise self.remove_error


def _light(device_id: str) -> DomainDevice:
    return DomainDevice(
        id=device_id, name="Lamp", device_type="light", capabilities={CapabilityType.ON_OFF: OnOffState(is_on=True)}
    )


# --- start_pairing -----------------------------------------------------------


async def test_start_pairing_forwards_the_duration_and_returns_current_snapshot():
    adapter = _FakeAdapter()
    adapter.devices = [_light("light-1")]
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    known_before = await service.start_pairing(actor, duration_seconds=120)

    assert known_before == {"light-1"}
    assert adapter.start_pairing_calls == [120]


async def test_start_pairing_defaults_to_sixty_seconds():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.start_pairing(actor)

    assert adapter.start_pairing_calls == [60]


async def test_start_pairing_without_permission_is_denied():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor()  # no permissions

    with pytest.raises(AuthorizationError):
        await service.start_pairing(actor)
    assert adapter.start_pairing_calls == []
    assert audit.events == []  # denied before any adapter call, nothing to audit as an attempt


async def test_start_pairing_success_is_audited():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.start_pairing(actor, duration_seconds=90)

    assert audit.events[-1]["action"] == "zigbee.pairing_started"
    assert audit.events[-1]["outcome"] == "success"
    assert audit.events[-1]["metadata"]["durationSeconds"] == 90


async def test_start_pairing_failure_is_audited():
    adapter = _FakeAdapter()
    adapter.start_pairing_error = RuntimeError("gateway unreachable")
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    with pytest.raises(RuntimeError):
        await service.start_pairing(actor)

    assert audit.events[-1]["action"] == "zigbee.pairing_failed"
    assert audit.events[-1]["outcome"] == "failure"


# --- discover_new_devices: "über reguläres Device Model" --------------------


async def test_discover_new_devices_returns_only_devices_absent_from_the_snapshot():
    adapter = _FakeAdapter()
    adapter.devices = [_light("light-1")]
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    known_before = await service.start_pairing(actor)
    adapter.devices.append(_light("light-2"))  # joined during the pairing window

    new_devices = await service.discover_new_devices(known_before=known_before)

    assert len(new_devices) == 1
    assert isinstance(new_devices[0], DomainDevice)  # plain device model, nothing Zigbee-specific
    assert new_devices[0].id == "light-2"


async def test_discover_new_devices_returns_empty_when_nothing_joined():
    adapter = _FakeAdapter()
    adapter.devices = [_light("light-1")]
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    known_before = await service.start_pairing(actor)
    new_devices = await service.discover_new_devices(known_before=known_before)

    assert new_devices == []


# --- remove_device -----------------------------------------------------------


async def test_remove_device_forwards_the_ieee():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.remove_device(actor, ieee="00:11:22:33:44:55:66:77")

    assert adapter.remove_calls == ["00:11:22:33:44:55:66:77"]


async def test_remove_device_without_permission_is_denied():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor()

    with pytest.raises(AuthorizationError):
        await service.remove_device(actor, ieee="00:11:22:33:44:55:66:77")
    assert adapter.remove_calls == []


async def test_remove_device_success_is_audited():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.remove_device(actor, ieee="00:11:22:33:44:55:66:77")

    assert audit.events[-1]["action"] == "zigbee.device_removed"
    assert audit.events[-1]["outcome"] == "success"
    assert audit.events[-1]["target_id"] == "00:11:22:33:44:55:66:77"


async def test_remove_device_failure_is_audited():
    adapter = _FakeAdapter()
    adapter.remove_error = RuntimeError("device not joined")
    audit = InMemoryAuditRecorder()
    service = ZigbeePairingService(adapter, audit)
    actor = make_actor("devices:manage")

    with pytest.raises(RuntimeError):
        await service.remove_device(actor, ieee="00:11:22:33:44:55:66:77")

    assert audit.events[-1]["action"] == "zigbee.device_remove_failed"
    assert audit.events[-1]["outcome"] == "failure"
