"""S1V2-02-019 Definition of Done: "Echte oder simulierte Geräte können
über SystemONE gesteuert werden" (the simulated half - see
test_ha_device_adapter.py for the real/mock-HA half) plus "Capability-
und Rechteprüfung vor Ausführung" and "Locks/Kameras ... durch
Haushalts-PIN-Policy schützen"."""

import pytest

from app.audit import InMemoryAuditRecorder
from app.auth import (
    AdminAreaService,
    FakeBiometricVerifier,
    HouseholdPinService,
    InvalidPinError,
    NoCredentialSuppliedError,
    ProtectedActionGuard,
)
from app.auth.sessions import SessionStore
from app.authorization import Actor, AuthorizationError
from app.domain.capabilities import (
    CapabilityType,
    LockState,
    OnOffState,
    SetLockCommand,
    SetOnOffCommand,
)
from app.domain.device import DomainDevice
from app.domain.errors import CapabilityNotSupportedError as DomainCapabilityNotSupportedError
from app.domain.errors import DeviceNotFoundError
from app.domain.service import DeviceService
from app.repositories.records import UserRecord
from app.services.device_commands import DeviceCommandService
from tests.fakes import FakeUnitOfWork


class _FakeDeviceAdapter:
    """Minimal DeviceAdapterPort fake seeded with a lock-capable device -
    SimulationDeviceAdapter (S1V2-02-002) deliberately isn't extended for
    lock/climate/camera (out of S1V2-02-018's scope), so this test file
    provides its own."""

    def __init__(self) -> None:
        self.devices: dict[str, DomainDevice] = {}

    def seed(self, device: DomainDevice) -> None:
        self.devices[device.id] = device

    async def list_devices(self) -> list[DomainDevice]:
        return list(self.devices.values())

    async def apply_command(self, device_id: str, command):
        device = self.devices[device_id]
        if command.type == CapabilityType.ON_OFF:
            new_state = OnOffState(is_on=command.is_on)
        elif command.type == CapabilityType.LOCK:
            new_state = LockState(is_locked=command.is_locked)
        else:  # pragma: no cover - not exercised by this test file
            raise DomainCapabilityNotSupportedError(device_id, str(command.type))
        device.capabilities[command.type] = new_state
        return new_state


@pytest.fixture
def rig():
    uow = FakeUnitOfWork()
    uow.users.add(
        UserRecord(
            id="user-1",
            household_id="hh-1",
            role_id="role-member",
            display_name="Household Member",
            password_hash=None,
            pin_hash=None,
        )
    )
    sessions = SessionStore()
    audit = InMemoryAuditRecorder()
    admin_area = AdminAreaService(
        uow_factory=lambda: uow, sessions=sessions, audit=audit, biometric_verifier=FakeBiometricVerifier()
    )
    pin_service = HouseholdPinService(uow_factory=lambda: uow, audit=audit, admin_area=admin_area)
    guard = ProtectedActionGuard(
        pin_service=pin_service, audit=audit, biometric_verifier=FakeBiometricVerifier(), uow_factory=lambda: uow
    )

    adapter = _FakeDeviceAdapter()
    adapter.seed(
        DomainDevice(
            id="light-1", name="Lamp", device_type="light", capabilities={CapabilityType.ON_OFF: OnOffState(is_on=False)}
        )
    )
    adapter.seed(
        DomainDevice(
            id="lock-1",
            name="Front Door",
            device_type="lock",
            capabilities={CapabilityType.LOCK: LockState(is_locked=True)},
        )
    )
    device_service = DeviceService(adapter)
    command_service = DeviceCommandService(device_service=device_service, protected_action_guard=guard, audit=audit)

    actor = Actor(user_id="user-1", household_id="hh-1", permissions=frozenset({"devices:control"}))
    return command_service, pin_service, audit, actor, uow


async def _enable_pin(pin_service, uow):
    admin = Actor(user_id="admin-1", household_id="hh-1", permissions=frozenset({"users:manage"}))
    uow.users.add(
        UserRecord(
            id="admin-1", household_id="hh-1", role_id="role-owner", display_name="Admin", password_hash=None, pin_hash=None
        )
    )
    await pin_service.enable_pin(admin, target_user_id="user-1", pin="4321")


# --- non-sensitive commands: no PIN required -------------------------------


async def test_non_sensitive_command_succeeds_without_any_credential(rig):
    command_service, _pin_service, _audit, actor, _uow = rig
    new_state = await command_service.send_command(actor, device_id="light-1", command=SetOnOffCommand(is_on=True))
    assert new_state == OnOffState(is_on=True)


# --- sensitive commands: fresh PIN required, no unlock session -------------


async def test_lock_command_without_any_credential_is_rejected(rig):
    command_service, _pin_service, _audit, actor, _uow = rig
    with pytest.raises(NoCredentialSuppliedError):
        await command_service.send_command(actor, device_id="lock-1", command=SetLockCommand(is_locked=False))


async def test_lock_command_with_correct_pin_succeeds(rig):
    command_service, pin_service, _audit, actor, uow = rig
    await _enable_pin(pin_service, uow)

    new_state = await command_service.send_command(
        actor, device_id="lock-1", command=SetLockCommand(is_locked=False), pin="4321"
    )
    assert new_state == LockState(is_locked=False)


async def test_lock_command_with_wrong_pin_is_rejected(rig):
    command_service, pin_service, _audit, actor, uow = rig
    await _enable_pin(pin_service, uow)

    with pytest.raises(InvalidPinError):
        await command_service.send_command(actor, device_id="lock-1", command=SetLockCommand(is_locked=False), pin="0000")


async def test_two_consecutive_lock_commands_each_require_their_own_fresh_pin(rig):
    """Ties S1V2-02-012's "keine Freischaltsession" guarantee directly to
    device commands: a successful lock command must not open any kind of
    window for the next one."""
    command_service, pin_service, _audit, actor, uow = rig
    await _enable_pin(pin_service, uow)

    await command_service.send_command(actor, device_id="lock-1", command=SetLockCommand(is_locked=False), pin="4321")

    with pytest.raises(NoCredentialSuppliedError):
        await command_service.send_command(actor, device_id="lock-1", command=SetLockCommand(is_locked=True))


# --- permission check -------------------------------------------------------


async def test_command_without_devices_control_permission_is_denied(rig):
    command_service, _pin_service, audit, _actor, _uow = rig
    unauthorized = Actor(user_id="user-1", household_id="hh-1", permissions=frozenset())

    with pytest.raises(AuthorizationError):
        await command_service.send_command(unauthorized, device_id="light-1", command=SetOnOffCommand(is_on=True))
    assert audit.events == []  # denied before any adapter call, nothing to audit as an attempt


# --- audit trail -------------------------------------------------------------


async def test_successful_command_is_audited(rig):
    command_service, _pin_service, audit, actor, _uow = rig
    await command_service.send_command(actor, device_id="light-1", command=SetOnOffCommand(is_on=True))

    assert audit.events[-1]["action"] == "device.command_executed"
    assert audit.events[-1]["target_id"] == "light-1"
    assert audit.events[-1]["metadata"]["capability"] == "on_off"


async def test_failed_command_is_audited_as_failure(rig):
    command_service, _pin_service, audit, actor, _uow = rig
    with pytest.raises(DeviceNotFoundError):
        await command_service.send_command(actor, device_id="never-existed", command=SetOnOffCommand(is_on=True))

    assert audit.events[-1]["action"] == "device.command_failed"
    assert audit.events[-1]["outcome"] == "failure"
