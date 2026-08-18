"""S1V2-02-011 Definition of Done: "Tests für richtige/falsche Eingaben,
Staffelung, fehlendes Benutzerrecht und Reset"."""

from datetime import UTC, datetime, timedelta

import pytest

from app.audit import InMemoryAuditRecorder
from app.auth import (
    AdminAreaLockedError,
    AdminAreaService,
    FakeBiometricVerifier,
    HouseholdPinService,
    InvalidPinError,
    InvalidPinFormatError,
    PinLockedError,
    PinNotEnabledError,
    SessionStore,
    hash_password,
)
from app.authorization import AuthorizationError
from app.repositories.records import UserRecord
from tests.fakes import FakeUnitOfWork, make_actor


@pytest.fixture
def rig():
    uow = FakeUnitOfWork()
    uow.users.add(
        UserRecord(
            id="user-1",
            household_id="hh-1",
            role_id="role-member",
            display_name="Household Member",
            password_hash=hash_password("owner-password-not-used-here"),
            pin_hash=None,
        )
    )
    sessions = SessionStore()
    audit = InMemoryAuditRecorder()
    admin_area = AdminAreaService(
        uow_factory=lambda: uow, sessions=sessions, audit=audit, biometric_verifier=FakeBiometricVerifier()
    )
    service = HouseholdPinService(uow_factory=lambda: uow, audit=audit, admin_area=admin_area)
    admin = make_actor("users:manage")
    return service, uow, audit, sessions, admin_area, admin


# --- fehlendes Benutzerrecht -----------------------------------------------


async def test_pin_verification_fails_when_user_has_no_pin_enabled(rig):
    service, _uow, _audit, _sessions, _admin_area, _admin = rig
    with pytest.raises(PinNotEnabledError):
        await service.verify_pin("user-1", "1234")


async def test_enable_pin_requires_users_manage_permission(rig):
    service, _uow, _audit, _sessions, _admin_area, _admin = rig
    unauthorized = make_actor()
    with pytest.raises(AuthorizationError):
        await service.enable_pin(unauthorized, target_user_id="user-1", pin="1234")


@pytest.mark.parametrize("bad_pin", ["123", "123456789", "12a4", "", "12 34"])
async def test_enable_pin_rejects_invalid_formats(rig, bad_pin):
    service, _uow, _audit, _sessions, _admin_area, admin = rig
    with pytest.raises(InvalidPinFormatError):
        await service.enable_pin(admin, target_user_id="user-1", pin=bad_pin)


# --- richtige/falsche Eingaben ----------------------------------------------


async def test_correct_pin_verifies_after_admin_enables_it(rig):
    service, _uow, audit, _sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")

    await service.verify_pin("user-1", "4321")  # must not raise
    assert audit.events[-1]["action"] == "pin.verified"


async def test_wrong_pin_is_rejected(rig):
    service, _uow, audit, _sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")

    with pytest.raises(InvalidPinError):
        await service.verify_pin("user-1", "0000")
    assert audit.events[-1]["action"] == "pin.verify_failed"


async def test_pin_is_never_stored_in_plaintext(rig):
    service, uow, _audit, _sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")
    stored = uow.users.get_by_id("user-1")
    assert stored.pin_hash != "4321"
    assert "4321" not in stored.pin_hash


# --- Staffelung (escalating lockout) ---------------------------------------


async def test_lockout_kicks_in_after_five_failures(rig):
    service, _uow, audit, _sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")
    t0 = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)

    for _ in range(5):
        with pytest.raises(InvalidPinError):
            await service.verify_pin("user-1", "0000", now=t0)

    remaining = service.is_locked("user-1", now=t0)
    assert remaining == timedelta(minutes=1)  # first stage
    with pytest.raises(PinLockedError):
        await service.verify_pin("user-1", "4321", now=t0)  # even the *correct* PIN is rejected while locked
    assert audit.events[-1]["action"] == "pin.attempt_while_locked"


async def test_lockout_stages_escalate_on_repeated_breaches(rig):
    service, _uow, _audit, _sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")
    t = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)

    # First lockout stage (1 minute).
    for _ in range(5):
        with pytest.raises(InvalidPinError):
            await service.verify_pin("user-1", "0000", now=t)
    assert service.is_locked("user-1", now=t) == timedelta(minutes=1)

    # Wait out stage 1, fail 5 more times -> stage 2 (5 minutes), strictly
    # longer than stage 1.
    t = t + timedelta(minutes=1, seconds=1)
    for _ in range(5):
        with pytest.raises(InvalidPinError):
            await service.verify_pin("user-1", "0000", now=t)
    second_stage_remaining = service.is_locked("user-1", now=t)
    assert second_stage_remaining == timedelta(minutes=5)
    assert second_stage_remaining > timedelta(minutes=1)


async def test_successful_verification_resets_the_failure_count_and_stage(rig):
    service, _uow, _audit, _sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")
    t = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)

    for _ in range(4):  # one short of the threshold
        with pytest.raises(InvalidPinError):
            await service.verify_pin("user-1", "0000", now=t)
    await service.verify_pin("user-1", "4321", now=t)  # success resets the counter
    assert service.is_locked("user-1", now=t) is None

    # A subsequent run of 4 failures alone still should not lock (counter
    # truly reset, not just "one away from before").
    for _ in range(4):
        with pytest.raises(InvalidPinError):
            await service.verify_pin("user-1", "0000", now=t)
    assert service.is_locked("user-1", now=t) is None


# --- Reset (nur nach erneuter Adminauthentifizierung) -----------------------


async def test_reset_lockout_requires_the_admins_own_admin_area_to_be_unlocked(rig):
    service, _uow, _audit, sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")
    t = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)
    for _ in range(5):
        with pytest.raises(InvalidPinError):
            await service.verify_pin("user-1", "0000", now=t)
    assert service.is_locked("user-1", now=t) is not None

    admin_token, _session = sessions.create(
        user_id="admin-1", permissions=frozenset({"users:manage"}), device_label="admin-phone", ttl=timedelta(hours=1)
    )
    # Admin has a valid *session* but has not freshly re-authenticated into
    # their own admin area - reset must still be refused.
    with pytest.raises(AdminAreaLockedError):
        await service.reset_lockout(admin, admin_token, target_user_id="user-1")
    assert service.is_locked("user-1", now=t) is not None  # unchanged


async def test_reset_lockout_succeeds_once_admin_freshly_unlocked(rig):
    service, uow, audit, sessions, admin_area, admin = rig
    uow.users.add(
        UserRecord(
            id="admin-1",
            household_id="hh-1",
            role_id="role-owner",
            display_name="Admin",
            password_hash=hash_password("admin-password"),
            pin_hash=None,
        )
    )
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")
    t = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)
    for _ in range(5):
        with pytest.raises(InvalidPinError):
            await service.verify_pin("user-1", "0000", now=t)
    assert service.is_locked("user-1", now=t) is not None

    admin_token, _session = sessions.create(
        user_id="admin-1", permissions=frozenset({"users:manage"}), device_label="admin-phone", ttl=timedelta(hours=1)
    )
    await admin_area.unlock_admin_area(admin_token, password="admin-password", now=t)

    await service.reset_lockout(admin, admin_token, target_user_id="user-1")

    assert service.is_locked("user-1", now=t) is None
    await service.verify_pin("user-1", "4321", now=t)  # PIN itself is unaffected by the lockout reset
    assert audit.events[-2]["action"] == "pin.lockout_reset"


async def test_reset_lockout_requires_users_manage_permission(rig):
    service, _uow, _audit, sessions, admin_area, _admin = rig
    unauthorized = make_actor()  # holds no permissions at all
    admin_token, _session = sessions.create(
        user_id="user-x", permissions=frozenset(), device_label="d", ttl=timedelta(hours=1)
    )

    with pytest.raises(AuthorizationError):
        await service.reset_lockout(unauthorized, admin_token, target_user_id="user-1")


# --- disable ----------------------------------------------------------------


async def test_disable_pin_removes_it_and_clears_any_lockout(rig):
    service, uow, _audit, _sessions, _admin_area, admin = rig
    await service.enable_pin(admin, target_user_id="user-1", pin="4321")

    await service.disable_pin(admin, target_user_id="user-1")

    assert uow.users.get_by_id("user-1").pin_hash is None
    with pytest.raises(PinNotEnabledError):
        await service.verify_pin("user-1", "4321")
