"""S1V2-02-023 Definition of Done (software half - see
docs/architecture/matter-integration.md's "Bekannte Grenzen" for why the
"mindestens ein reales Matter-Gerät" hardware half cannot be verified in
this environment): permission-gated commissioning/removal, audit trail on
both success and failure, "Geräte erscheinen über reguläres Device Model".

Uses a bare double for TranslatingHomeAssistantAdapter, mirroring
test_zigbee_pairing.py's shape - this service only ever calls
list_devices()/start_matter_commissioning_*()/remove_matter_device() on
it (structural typing), so a double satisfying that surface is a faithful
substitute without a real Home Assistant or Matter controller."""

import pytest

from app.audit import InMemoryAuditRecorder
from app.authorization import AuthorizationError
from app.domain.capabilities import CapabilityType, OnOffState
from app.domain.device import DomainDevice
from app.services.matter_commissioning import MatterCommissioningService
from tests.fakes import make_actor


class _FakeAdapter:
    def __init__(self) -> None:
        self.devices: list[DomainDevice] = []
        self.commission_with_code_calls: list[tuple[str, bool]] = []
        self.commission_on_network_calls: list[tuple[int, str | None]] = []
        self.remove_calls: list[tuple[str, int]] = []
        self.commission_error: Exception | None = None
        self.remove_error: Exception | None = None

    async def list_devices(self) -> list[DomainDevice]:
        return list(self.devices)

    async def start_matter_commissioning_with_code(self, *, code: str, network_only: bool = True) -> None:
        self.commission_with_code_calls.append((code, network_only))
        if self.commission_error is not None:
            raise self.commission_error

    async def start_matter_commissioning_on_network(self, *, pin: int, ip_addr: str | None = None) -> None:
        self.commission_on_network_calls.append((pin, ip_addr))
        if self.commission_error is not None:
            raise self.commission_error

    async def remove_matter_device(self, *, device_id: str, fabric_index: int) -> None:
        self.remove_calls.append((device_id, fabric_index))
        if self.remove_error is not None:
            raise self.remove_error


def _light(device_id: str) -> DomainDevice:
    return DomainDevice(
        id=device_id, name="Lamp", device_type="light", capabilities={CapabilityType.ON_OFF: OnOffState(is_on=True)}
    )


# --- start_commissioning_with_code ------------------------------------------


async def test_start_commissioning_with_code_forwards_the_code_and_returns_snapshot():
    adapter = _FakeAdapter()
    adapter.devices = [_light("light-1")]
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    known_before = await service.start_commissioning_with_code(actor, code="MT:ABCDEF", network_only=False)

    assert known_before == {"light-1"}
    assert adapter.commission_with_code_calls == [("MT:ABCDEF", False)]


async def test_start_commissioning_with_code_without_permission_is_denied():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor()

    with pytest.raises(AuthorizationError):
        await service.start_commissioning_with_code(actor, code="MT:ABCDEF")
    assert adapter.commission_with_code_calls == []
    assert audit.events == []


async def test_start_commissioning_with_code_success_is_audited():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.start_commissioning_with_code(actor, code="MT:ABCDEF")

    assert audit.events[-1]["action"] == "matter.commissioning_started"
    assert audit.events[-1]["outcome"] == "success"
    assert audit.events[-1]["metadata"]["method"] == "code"


async def test_start_commissioning_with_code_failure_is_audited():
    adapter = _FakeAdapter()
    adapter.commission_error = RuntimeError("invalid code")
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    with pytest.raises(RuntimeError):
        await service.start_commissioning_with_code(actor, code="MT:BADCODE")

    assert audit.events[-1]["action"] == "matter.commissioning_failed"
    assert audit.events[-1]["outcome"] == "failure"


# --- start_commissioning_on_network -----------------------------------------


async def test_start_commissioning_on_network_forwards_the_pin():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.start_commissioning_on_network(actor, pin=12345678, ip_addr="192.168.1.42")

    assert adapter.commission_on_network_calls == [(12345678, "192.168.1.42")]


async def test_start_commissioning_on_network_without_permission_is_denied():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor()

    with pytest.raises(AuthorizationError):
        await service.start_commissioning_on_network(actor, pin=12345678)
    assert adapter.commission_on_network_calls == []


# --- discover_new_devices: "über reguläres Device Model" --------------------


async def test_discover_new_devices_returns_only_devices_absent_from_the_snapshot():
    adapter = _FakeAdapter()
    adapter.devices = [_light("light-1")]
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    known_before = await service.start_commissioning_with_code(actor, code="MT:ABCDEF")
    adapter.devices.append(_light("light-2"))  # joined during commissioning

    new_devices = await service.discover_new_devices(known_before=known_before)

    assert len(new_devices) == 1
    assert isinstance(new_devices[0], DomainDevice)
    assert new_devices[0].id == "light-2"


async def test_discover_new_devices_returns_empty_when_nothing_joined():
    adapter = _FakeAdapter()
    adapter.devices = [_light("light-1")]
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    known_before = await service.start_commissioning_with_code(actor, code="MT:ABCDEF")
    new_devices = await service.discover_new_devices(known_before=known_before)

    assert new_devices == []


# --- remove_device -----------------------------------------------------------


async def test_remove_device_forwards_device_id_and_fabric_index():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.remove_device(actor, device_id="light-1", fabric_index=1)

    assert adapter.remove_calls == [("light-1", 1)]


async def test_remove_device_without_permission_is_denied():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor()

    with pytest.raises(AuthorizationError):
        await service.remove_device(actor, device_id="light-1", fabric_index=1)
    assert adapter.remove_calls == []


async def test_remove_device_success_is_audited():
    adapter = _FakeAdapter()
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    await service.remove_device(actor, device_id="light-1", fabric_index=1)

    assert audit.events[-1]["action"] == "matter.device_removed"
    assert audit.events[-1]["outcome"] == "success"
    assert audit.events[-1]["target_id"] == "light-1"


async def test_remove_device_failure_is_audited():
    adapter = _FakeAdapter()
    adapter.remove_error = RuntimeError("device not commissioned")
    audit = InMemoryAuditRecorder()
    service = MatterCommissioningService(adapter, audit)
    actor = make_actor("devices:manage")

    with pytest.raises(RuntimeError):
        await service.remove_device(actor, device_id="light-1", fabric_index=1)

    assert audit.events[-1]["action"] == "matter.device_remove_failed"
    assert audit.events[-1]["outcome"] == "failure"
