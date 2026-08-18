"""S1V2-02-010 Definition of Done: "Tests für Zeitablauf, Hintergrund,
manipulierte Clients und erneute Freigabe" (backend/service layer - no
Flutter app or API routes exist yet to attach equivalent tests to; the
enforcement logic tested here is what those layers will call into
unchanged, per the pattern established throughout this codebase)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.audit import InMemoryAuditRecorder
from app.auth import (
    AdminAreaLockedError,
    AdminAreaService,
    FakeBiometricVerifier,
    SessionStore,
    StepUpAuthenticationError,
    hash_password,
)
from app.repositories.records import UserRecord
from tests.fakes import FakeUnitOfWork

pytestmark = pytest.mark.security


@pytest.fixture
def rig():
    uow = FakeUnitOfWork()
    uow.users.add(
        UserRecord(
            id="user-1",
            household_id="hh-1",
            role_id="role-owner",
            display_name="Owner",
            password_hash=hash_password("correct horse battery staple"),
            pin_hash=None,
        )
    )
    sessions = SessionStore()
    raw_token, _session = sessions.create(
        user_id="user-1", household_id="hh-1", permissions=frozenset({"users:manage"}), device_label="phone", ttl=timedelta(hours=1)
    )
    audit = InMemoryAuditRecorder()
    biometrics = FakeBiometricVerifier()
    service = AdminAreaService(uow_factory=lambda: uow, sessions=sessions, audit=audit, biometric_verifier=biometrics)
    return service, sessions, audit, biometrics, raw_token


# --- everyday control needs no admin unlock -------------------------------


def test_a_fresh_session_is_locked_out_of_the_admin_area_by_default(rig):
    """"Alltagssteuerung darf standardmäßig ohne erneute Passwortabfrage
    öffnen" - but the admin area itself starts locked; base session
    validity alone (already proven in S1V2-02-008) is not enough."""
    service, _sessions, _audit, _biometrics, raw_token = rig
    assert service.is_unlocked(raw_token) is False
    with pytest.raises(AdminAreaLockedError):
        service.require_unlocked(raw_token)


# --- erneute Freigabe (fresh authorization) -------------------------------


async def test_unlock_with_correct_password_grants_admin_access(rig):
    service, _sessions, audit, _biometrics, raw_token = rig

    await service.unlock_admin_area(raw_token, password="correct horse battery staple")

    service.require_unlocked(raw_token)  # must not raise
    assert audit.events[-1]["action"] == "admin_area.unlocked"
    assert audit.events[-1]["metadata"]["method"] == "password"


async def test_unlock_with_valid_biometric_assertion_grants_admin_access(rig):
    service, _sessions, _audit, biometrics, raw_token = rig
    biometrics.register_valid_assertion("device-signed-assertion-xyz", user_id="user-1")

    await service.unlock_admin_area(raw_token, biometric_assertion="device-signed-assertion-xyz")

    service.require_unlocked(raw_token)  # must not raise


# --- manipulierte Clients --------------------------------------------------


async def test_wrong_password_does_not_unlock(rig):
    service, _sessions, audit, _biometrics, raw_token = rig

    with pytest.raises(StepUpAuthenticationError):
        await service.unlock_admin_area(raw_token, password="totally wrong")

    assert service.is_unlocked(raw_token) is False
    assert audit.events[-1]["action"] == "admin_area.stepup_failed"


async def test_forged_biometric_assertion_does_not_unlock(rig):
    """A manipulated client sending an assertion it made up (never
    registered as valid by the verifier) must not succeed."""
    service, _sessions, _audit, _biometrics, raw_token = rig

    with pytest.raises(StepUpAuthenticationError):
        await service.unlock_admin_area(raw_token, biometric_assertion="i-just-made-this-up")

    assert service.is_unlocked(raw_token) is False


async def test_biometric_assertion_registered_for_a_different_user_does_not_unlock(rig):
    """A client cannot reuse someone else's valid assertion for this
    session's user."""
    service, _sessions, _audit, biometrics, raw_token = rig
    biometrics.register_valid_assertion("someone-elses-assertion", user_id="a-different-user")

    with pytest.raises(StepUpAuthenticationError):
        await service.unlock_admin_area(raw_token, biometric_assertion="someone-elses-assertion")


async def test_unlock_call_with_neither_password_nor_biometric_is_rejected(rig):
    service, _sessions, _audit, _biometrics, raw_token = rig
    with pytest.raises(StepUpAuthenticationError):
        await service.unlock_admin_area(raw_token)


def test_admin_action_without_ever_unlocking_is_blocked(rig):
    """A client that simply skips the unlock call and goes straight for an
    admin action must be blocked - the server never trusts a client-
    asserted "I'm unlocked" flag because there isn't one; state lives only
    server-side."""
    service, _sessions, audit, _biometrics, raw_token = rig

    with pytest.raises(AdminAreaLockedError):
        service.require_unlocked(raw_token)
    assert audit.events[-1]["action"] == "admin_area.blocked_while_locked"


async def test_a_revoked_session_cannot_unlock_the_admin_area(rig):
    service, sessions, _audit, _biometrics, raw_token = rig
    sessions.revoke(raw_token)

    with pytest.raises(AdminAreaLockedError):
        await service.unlock_admin_area(raw_token, password="correct horse battery staple")


# --- Zeitablauf (inactivity timeout) ---------------------------------------


async def test_admin_area_relocks_after_five_minutes_of_inactivity(rig):
    service, _sessions, _audit, _biometrics, raw_token = rig
    t0 = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)
    await service.unlock_admin_area(raw_token, password="correct horse battery staple", now=t0)

    # Non-mutating check (is_unlocked does not touch/extend the window,
    # unlike require_unlocked) so it doesn't reset the clock we're testing.
    still_within_window = t0 + timedelta(minutes=4, seconds=59)
    assert service.is_unlocked(raw_token, now=still_within_window) is True

    past_the_window = t0 + timedelta(minutes=5, seconds=1)
    with pytest.raises(AdminAreaLockedError):
        service.require_unlocked(raw_token, now=past_the_window)


async def test_continued_activity_extends_the_inactivity_window(rig):
    """Each admin-area action resets the 5-minute clock, so a user actively
    working in settings isn't kicked out mid-task."""
    service, _sessions, _audit, _biometrics, raw_token = rig
    t0 = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)
    await service.unlock_admin_area(raw_token, password="correct horse battery staple", now=t0)

    almost_expired = t0 + timedelta(minutes=4, seconds=50)
    service.require_unlocked(raw_token, now=almost_expired)  # touches -> resets window

    still_alive_after_the_original_deadline = t0 + timedelta(minutes=9, seconds=40)
    service.require_unlocked(raw_token, now=still_alive_after_the_original_deadline)  # must not raise


# --- Hintergrund (app backgrounded / admin area left) ----------------------


async def test_locking_on_background_immediately_revokes_admin_access(rig):
    service, _sessions, audit, _biometrics, raw_token = rig
    await service.unlock_admin_area(raw_token, password="correct horse battery staple")
    service.require_unlocked(raw_token)  # confirms it was unlocked

    service.lock(raw_token, reason="app_backgrounded")
    assert audit.events[-1]["action"] == "admin_area.locked"
    assert audit.events[-1]["metadata"]["reason"] == "app_backgrounded"

    with pytest.raises(AdminAreaLockedError):
        service.require_unlocked(raw_token)
    assert audit.events[-1]["action"] == "admin_area.blocked_while_locked"


async def test_unlock_after_a_background_lock_works_again(rig):
    """Erneute Freigabe: after being locked out (background/timeout), a
    fresh, correctly-verified unlock call restores access."""
    service, _sessions, _audit, _biometrics, raw_token = rig
    await service.unlock_admin_area(raw_token, password="correct horse battery staple")
    service.lock(raw_token, reason="app_backgrounded")

    await service.unlock_admin_area(raw_token, password="correct horse battery staple")

    service.require_unlocked(raw_token)  # must not raise
