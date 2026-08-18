"""S1V2-02-012 Definition of Done: "Zwei aufeinanderfolgende geschützte
Aktionen verlangen jeweils neue Freigabe" - proven below by showing that a
successful authorize_action() call for one protected action never allows a
second, later action to skip its own PIN/biometric check."""

from datetime import UTC, datetime, timedelta

import pytest

from app.audit import InMemoryAuditRecorder
from app.auth import (
    AdminAreaService,
    BiometricNotAllowedError,
    BiometricVerificationFailedError,
    FakeBiometricVerifier,
    HouseholdPinService,
    InvalidPinError,
    NoCredentialSuppliedError,
    PinLockedError,
    ProtectedActionGuard,
    SessionStore,
    hash_password,
)
from app.authorization import AuthorizationError
from app.repositories.records import UserRecord
from tests.fakes import FakeUnitOfWork, make_actor

pytestmark = pytest.mark.security

CAMERA_VIEW = "camera:view"
LOCK_UNLOCK = "lock:unlock"


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
    biometric_verifier = FakeBiometricVerifier()
    guard = ProtectedActionGuard(
        pin_service=pin_service, audit=audit, biometric_verifier=biometric_verifier, uow_factory=lambda: uow
    )
    admin = make_actor("users:manage")
    actor = make_actor(CAMERA_VIEW, LOCK_UNLOCK)
    return guard, pin_service, audit, biometric_verifier, admin, actor


# --- keine Freischaltsession: zwei aufeinanderfolgende Aktionen -------------


async def test_two_consecutive_actions_each_require_their_own_fresh_pin(rig):
    guard, pin_service, _audit, _bio, admin, actor = rig
    await pin_service.enable_pin(admin, target_user_id="user-1", pin="4321")

    await guard.authorize_action(
        actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", pin="4321"
    )
    # Repeating the action without a credential fails - the first
    # successful authorization did not open any kind of session/window.
    with pytest.raises(NoCredentialSuppliedError):
        await guard.authorize_action(actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view")

    # Supplying the correct PIN again succeeds again - proving each call is
    # independently verified, not blocked by "already used".
    await guard.authorize_action(
        actor, target_user_id="user-1", permission=LOCK_UNLOCK, action="lock.unlock", pin="4321"
    )


async def test_wrong_pin_on_the_second_action_is_rejected_even_after_a_correct_first(rig):
    guard, pin_service, _audit, _bio, admin, actor = rig
    await pin_service.enable_pin(admin, target_user_id="user-1", pin="4321")

    await guard.authorize_action(
        actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", pin="4321"
    )
    with pytest.raises(InvalidPinError):
        await guard.authorize_action(
            actor, target_user_id="user-1", permission=LOCK_UNLOCK, action="lock.unlock", pin="0000"
        )


async def test_no_credential_supplied_is_rejected(rig):
    guard, pin_service, _audit, _bio, admin, actor = rig
    await pin_service.enable_pin(admin, target_user_id="user-1", pin="4321")
    with pytest.raises(NoCredentialSuppliedError):
        await guard.authorize_action(actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view")


async def test_lockout_from_the_underlying_pin_service_still_applies(rig):
    guard, pin_service, _audit, _bio, admin, actor = rig
    await pin_service.enable_pin(admin, target_user_id="user-1", pin="4321")
    t = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)

    for _ in range(5):
        with pytest.raises(InvalidPinError):
            await guard.authorize_action(
                actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", pin="0000"
            )
    with pytest.raises(PinLockedError):
        await guard.authorize_action(
            actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", pin="4321"
        )


# --- Biometrie ersetzt nur Eingabe, nie Berechtigungsprüfung ----------------


async def test_biometric_is_rejected_until_an_admin_allows_it_for_the_user(rig):
    guard, _pin_service, _audit, biometric_verifier, _admin, actor = rig
    biometric_verifier.register_valid_assertion("assertion-1", user_id="user-1")

    with pytest.raises(BiometricNotAllowedError):
        await guard.authorize_action(
            actor,
            target_user_id="user-1",
            permission=CAMERA_VIEW,
            action="camera.view",
            biometric_assertion="assertion-1",
        )


async def test_biometric_succeeds_once_admin_allows_it(rig):
    guard, _pin_service, audit, biometric_verifier, admin, actor = rig
    biometric_verifier.register_valid_assertion("assertion-1", user_id="user-1")
    guard.allow_biometric(admin, target_user_id="user-1")

    await guard.authorize_action(
        actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", biometric_assertion="assertion-1"
    )
    assert audit.events[-1]["action"] == "protected_action.authorized"
    assert audit.events[-1]["metadata"]["method"] == "biometric"


async def test_biometric_still_requires_its_own_fresh_assertion_for_a_second_action(rig):
    guard, _pin_service, _audit, biometric_verifier, admin, actor = rig
    biometric_verifier.register_valid_assertion("assertion-1", user_id="user-1")
    guard.allow_biometric(admin, target_user_id="user-1")

    await guard.authorize_action(
        actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", biometric_assertion="assertion-1"
    )
    # No credential on the second call - even though the first biometric
    # check just succeeded, there is no session it could have opened.
    with pytest.raises(NoCredentialSuppliedError):
        await guard.authorize_action(actor, target_user_id="user-1", permission=LOCK_UNLOCK, action="lock.unlock")


async def test_unregistered_biometric_assertion_is_rejected(rig):
    guard, _pin_service, _audit, _bio, admin, actor = rig
    guard.allow_biometric(admin, target_user_id="user-1")

    with pytest.raises(BiometricVerificationFailedError):
        await guard.authorize_action(
            actor,
            target_user_id="user-1",
            permission=CAMERA_VIEW,
            action="camera.view",
            biometric_assertion="forged-assertion",
        )


async def test_biometric_success_does_not_bypass_the_underlying_permission_check(rig):
    """"Biometrie ersetzt nur Eingabe, nie Berechtigungsprüfung": a verified
    biometric assertion from a user who lacks the permission for this
    specific action must still be denied."""
    guard, _pin_service, _audit, biometric_verifier, admin, _actor = rig
    biometric_verifier.register_valid_assertion("assertion-1", user_id="user-1")
    guard.allow_biometric(admin, target_user_id="user-1")
    unauthorized_actor = make_actor()  # holds no permissions at all

    with pytest.raises(AuthorizationError):
        await guard.authorize_action(
            unauthorized_actor,
            target_user_id="user-1",
            permission=CAMERA_VIEW,
            action="camera.view",
            biometric_assertion="assertion-1",
        )


async def test_disallow_biometric_revokes_a_previously_granted_allowance(rig):
    guard, _pin_service, _audit, biometric_verifier, admin, actor = rig
    biometric_verifier.register_valid_assertion("assertion-1", user_id="user-1")
    guard.allow_biometric(admin, target_user_id="user-1")
    guard.disallow_biometric(admin, target_user_id="user-1")

    with pytest.raises(BiometricNotAllowedError):
        await guard.authorize_action(
            actor,
            target_user_id="user-1",
            permission=CAMERA_VIEW,
            action="camera.view",
            biometric_assertion="assertion-1",
        )


async def test_allow_biometric_requires_users_manage_permission(rig):
    guard, _pin_service, _audit, _bio, _admin, _actor = rig
    unauthorized = make_actor()
    with pytest.raises(AuthorizationError):
        guard.allow_biometric(unauthorized, target_user_id="user-1")


# --- vergessene PIN: neu setzen statt wiederherstellen -----------------------


async def test_forgotten_pin_is_reset_by_an_admin_setting_a_new_one_not_recovering_the_old(rig):
    guard, pin_service, _audit, _bio, admin, actor = rig
    await pin_service.enable_pin(admin, target_user_id="user-1", pin="4321")

    # "Vergessen": the admin sets a brand new PIN - there is no code path
    # that reveals or restores the original one.
    await pin_service.enable_pin(admin, target_user_id="user-1", pin="9999")

    with pytest.raises(InvalidPinError):
        await guard.authorize_action(
            actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", pin="4321"
        )
    await guard.authorize_action(
        actor, target_user_id="user-1", permission=CAMERA_VIEW, action="camera.view", pin="9999"
    )
