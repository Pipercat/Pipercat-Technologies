"""S1V2-02-015 "Datenisolation" / "manipulierte IDs": negative tests
proving that holding a permission (e.g. users:manage, rooms:manage) does
not by itself authorize acting on a resource belonging to a *different*
household - only the combination of the right permission AND the right
household is accepted.

This gap was found while building the security-testharness task itself:
Actor previously had no household_id at all, and every service that
accepted a caller-supplied household_id or resolved one from a target
resource trusted it unconditionally. Fixed alongside these tests by
adding Actor.household_id and require_same_household() (see
app/authorization.py) - "Jede später gefundene Lücke erhält zuerst
Regressionstest" (AGENTS.md workflow), which these tests are.
"""

import pytest

from app.audit import InMemoryAuditRecorder
from app.auth import (
    AdminAreaService,
    FakeBiometricVerifier,
    HouseholdPinService,
    ProtectedActionGuard,
)
from app.auth.sessions import SessionStore
from app.authorization import CrossHouseholdAccessError
from app.repositories.records import UserRecord
from app.roles import RoleManagementService
from app.services.device_registration import DeviceRegistrationService
from app.services.rooms import RoomService
from tests.fakes import FakeUnitOfWork, make_actor

pytestmark = pytest.mark.security

HOUSEHOLD_A = "household-a"
HOUSEHOLD_B = "household-b"


# --- RoomService / DeviceRegistrationService: caller-supplied household_id -


def test_create_room_in_a_different_household_is_rejected():
    uow = FakeUnitOfWork()
    service = RoomService(uow_factory=lambda: uow, audit=InMemoryAuditRecorder())
    actor = make_actor("rooms:manage", household_id=HOUSEHOLD_A)

    with pytest.raises(CrossHouseholdAccessError):
        service.create_room(actor, household_id=HOUSEHOLD_B, name="Enemy Living Room")

    assert uow.rooms.list_by_household(HOUSEHOLD_B) == []


def test_list_rooms_of_a_different_household_is_rejected():
    uow = FakeUnitOfWork()
    service = RoomService(uow_factory=lambda: uow, audit=InMemoryAuditRecorder())
    owner_of_b = make_actor("rooms:manage", "rooms:read", household_id=HOUSEHOLD_B)
    service.create_room(owner_of_b, household_id=HOUSEHOLD_B, name="Kitchen")

    attacker = make_actor("rooms:read", household_id=HOUSEHOLD_A)
    with pytest.raises(CrossHouseholdAccessError):
        service.list_rooms(attacker, household_id=HOUSEHOLD_B)


def test_register_device_in_a_different_household_is_rejected():
    uow = FakeUnitOfWork()
    service = DeviceRegistrationService(uow_factory=lambda: uow, audit=InMemoryAuditRecorder())
    actor = make_actor("devices:manage", household_id=HOUSEHOLD_A)

    with pytest.raises(CrossHouseholdAccessError):
        service.register_device(
            actor,
            household_id=HOUSEHOLD_B,
            integration_id="int-1",
            external_id="lock.front_door",
            name="Front Door Lock",
            device_type="lock",
        )

    assert uow.devices.list_by_household(HOUSEHOLD_B) == []


# --- RoleManagementService: target_user_id resolved from the database -----


@pytest.fixture
def role_rig():
    uow = FakeUnitOfWork()
    uow.roles.add("administrator", "role-admin-id")
    uow.users.seed(
        UserRecord(
            id="victim-in-b",
            household_id=HOUSEHOLD_B,
            role_id="role-member-id",
            display_name="Victim",
            password_hash=None,
            pin_hash=None,
        )
    )
    audit = InMemoryAuditRecorder()
    service = RoleManagementService(uow_factory=lambda: uow, audit=audit)
    return service, uow, audit


async def test_assign_role_to_a_user_in_a_different_household_is_rejected(role_rig):
    """An actor holding users:manage in household A must not be able to
    change a role for a user who actually belongs to household B, even
    though the permission check alone would allow it."""
    service, uow, audit = role_rig
    attacker = make_actor("users:manage", household_id=HOUSEHOLD_A)

    with pytest.raises(CrossHouseholdAccessError):
        await service.assign_role(attacker, target_user_id="victim-in-b", role_key="administrator")

    assert uow.users.get_by_id("victim-in-b").role_id == "role-member-id"  # unchanged
    assert audit.events[-1]["action"] == "roles.assignment_blocked"
    assert audit.events[-1]["metadata"]["reason"] == "cross_household"


# --- HouseholdPinService: target_user_id resolved from the database -------


@pytest.fixture
def pin_rig():
    uow = FakeUnitOfWork()
    uow.users.seed(
        UserRecord(
            id="victim-in-b",
            household_id=HOUSEHOLD_B,
            role_id="role-member",
            display_name="Victim",
            password_hash=None,
            pin_hash=None,
        )
    )
    sessions = SessionStore()
    audit = InMemoryAuditRecorder()
    admin_area = AdminAreaService(
        uow_factory=lambda: uow, sessions=sessions, audit=audit, biometric_verifier=FakeBiometricVerifier()
    )
    service = HouseholdPinService(uow_factory=lambda: uow, audit=audit, admin_area=admin_area)
    return service, uow, audit


async def test_enable_pin_for_a_user_in_a_different_household_is_rejected(pin_rig):
    service, uow, audit = pin_rig
    attacker = make_actor("users:manage", household_id=HOUSEHOLD_A)

    with pytest.raises(CrossHouseholdAccessError):
        await service.enable_pin(attacker, target_user_id="victim-in-b", pin="1234")

    assert uow.users.get_by_id("victim-in-b").pin_hash is None
    assert audit.events[-1]["metadata"]["reason"] == "cross_household"


async def test_disable_pin_for_a_user_in_a_different_household_is_rejected(pin_rig):
    service, _uow, _audit = pin_rig
    attacker = make_actor("users:manage", household_id=HOUSEHOLD_A)

    with pytest.raises(CrossHouseholdAccessError):
        await service.disable_pin(attacker, target_user_id="victim-in-b")


# --- ProtectedActionGuard: target_user_id resolved from the database ------


@pytest.fixture
def protected_action_rig():
    uow = FakeUnitOfWork()
    uow.users.seed(
        UserRecord(
            id="victim-in-b",
            household_id=HOUSEHOLD_B,
            role_id="role-member",
            display_name="Victim",
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
        pin_service=pin_service,
        audit=audit,
        biometric_verifier=FakeBiometricVerifier(),
        uow_factory=lambda: uow,
    )
    return guard, uow, audit


async def test_authorize_action_against_a_user_in_a_different_household_is_rejected(protected_action_rig):
    guard, _uow, _audit = protected_action_rig
    attacker = make_actor("camera:view", household_id=HOUSEHOLD_A)

    with pytest.raises(CrossHouseholdAccessError):
        await guard.authorize_action(
            attacker, target_user_id="victim-in-b", permission="camera:view", action="camera.view", pin="0000"
        )


async def test_allow_biometric_for_a_user_in_a_different_household_is_rejected(protected_action_rig):
    guard, _uow, _audit = protected_action_rig
    attacker = make_actor("users:manage", household_id=HOUSEHOLD_A)

    with pytest.raises(CrossHouseholdAccessError):
        guard.allow_biometric(attacker, target_user_id="victim-in-b")

    assert guard.is_biometric_allowed("victim-in-b") is False
