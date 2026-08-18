"""S1V2-02-008 Definition of Done: "Security-Tests für falsche Passwörter,
Widerruf, Ablauf, CSRF/Rate-Limit und Rechteüberschreitung"."""

from datetime import timedelta

import pytest

from app.audit import InMemoryAuditRecorder
from app.auth import (
    AuthenticationService,
    CsrfValidationError,
    InvalidCredentialsError,
    RateLimitExceededError,
    RateLimiter,
    SessionExpiredError,
    SessionRevokedError,
    SessionStore,
    hash_password,
    validate_csrf,
    verify_password,
)
from app.authorization import AuthorizationError, WildcardPermissionError, require_permission, Actor
from app.repositories.records import UserRecord
from tests.fakes import FakeUnitOfWork

pytestmark = pytest.mark.security


ROLE_MEMBER = "role-member"


@pytest.fixture
def rig():
    uow = FakeUnitOfWork()
    uow.users.add(
        UserRecord(
            id="user-1",
            household_id="hh-1",
            role_id=ROLE_MEMBER,
            display_name="Test User",
            password_hash=hash_password("correct horse battery staple"),
            pin_hash=None,
        )
    )
    uow.users.set_role_permissions(ROLE_MEMBER, frozenset({"rooms:read"}))

    audit = InMemoryAuditRecorder()
    rate_limiter = RateLimiter(max_attempts=3, window_seconds=60.0)
    sessions = SessionStore()
    service = AuthenticationService(
        uow_factory=lambda: uow, sessions=sessions, audit=audit, rate_limiter=rate_limiter
    )
    return service, uow, audit, sessions, rate_limiter


# --- password hashing --------------------------------------------------


def test_password_hash_is_not_plaintext_and_verifies_correctly():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


# --- falsche Passwörter --------------------------------------------------


async def test_login_with_wrong_password_fails(rig):
    service, _uow, audit, _sessions, _rl = rig
    with pytest.raises(InvalidCredentialsError):
        await service.login(user_id="user-1", password="totally wrong", device_label="test-device")
    assert audit.events[-1]["action"] == "auth.login_failed"
    assert audit.events[-1]["outcome"] == "failure"


async def test_login_with_unknown_user_fails_with_the_same_error_type(rig):
    """Same exception type/message shape for unknown-user vs. wrong-password
    - a real API layer must not let this distinguish "user doesn't exist"
    from "wrong password" (user enumeration)."""
    service, _uow, _audit, _sessions, _rl = rig
    with pytest.raises(InvalidCredentialsError) as wrong_password_exc:
        await service.login(user_id="user-1", password="nope", device_label="d")
    with pytest.raises(InvalidCredentialsError) as unknown_user_exc:
        await service.login(user_id="does-not-exist", password="nope", device_label="d")
    assert str(wrong_password_exc.value) == str(unknown_user_exc.value)


async def test_login_with_correct_password_succeeds(rig):
    service, _uow, audit, _sessions, _rl = rig
    token, actor = await service.login(user_id="user-1", password="correct horse battery staple", device_label="d")

    assert token
    assert actor.user_id == "user-1"
    assert actor.permissions == frozenset({"rooms:read"})
    assert audit.events[-1]["action"] == "auth.login_succeeded"


# --- Rate-Limit --------------------------------------------------------


async def test_rate_limit_blocks_after_too_many_failed_attempts(rig):
    service, _uow, audit, _sessions, _rl = rig
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            await service.login(user_id="user-1", password="wrong", device_label="d")

    with pytest.raises(RateLimitExceededError):
        await service.login(user_id="user-1", password="wrong", device_label="d")
    assert audit.events[-1]["action"] == "auth.login_rate_limited"

    # Even the *correct* password is blocked once the limit is hit - the
    # limiter protects against brute force regardless of the final guess.
    with pytest.raises(RateLimitExceededError):
        await service.login(user_id="user-1", password="correct horse battery staple", device_label="d")


async def test_successful_login_resets_the_rate_limit(rig):
    service, _uow, _audit, _sessions, _rl = rig
    for _ in range(2):
        with pytest.raises(InvalidCredentialsError):
            await service.login(user_id="user-1", password="wrong", device_label="d")

    await service.login(user_id="user-1", password="correct horse battery staple", device_label="d")

    # Fresh budget of attempts after a success.
    for _ in range(2):
        with pytest.raises(InvalidCredentialsError):
            await service.login(user_id="user-1", password="wrong", device_label="d")
    # third failed attempt still allowed (budget was reset, not exhausted)
    with pytest.raises(InvalidCredentialsError):
        await service.login(user_id="user-1", password="wrong", device_label="d")


# --- Ablauf (expiry) -----------------------------------------------------


async def test_authenticate_with_expired_session_fails(rig):
    service, uow, audit, sessions, _rl = rig
    # ttl in the past -> immediately expired, no need to sleep in a test.
    raw_token, _session = sessions.create(
        user_id="user-1", household_id="hh-1", permissions=frozenset({"rooms:read"}), device_label="d", ttl=timedelta(seconds=-1)
    )

    with pytest.raises(SessionExpiredError):
        await service.authenticate(raw_token)
    assert audit.events[-1]["action"] == "auth.session_use_after_expiry"


# --- Widerruf (revocation) ------------------------------------------------


async def test_authenticate_with_revoked_session_fails(rig):
    service, _uow, audit, _sessions, _rl = rig
    token, _actor = await service.login(user_id="user-1", password="correct horse battery staple", device_label="d")

    await service.logout(token)

    with pytest.raises(SessionRevokedError):
        await service.authenticate(token)
    assert audit.events[-1]["action"] == "auth.session_use_after_revocation"


async def test_session_rotation_invalidates_the_old_token(rig):
    _service, _uow, _audit, sessions, _rl = rig
    raw_token, _session = sessions.create(
        user_id="user-1", household_id="hh-1", permissions=frozenset({"rooms:read"}), device_label="d", ttl=timedelta(hours=1)
    )

    rotated = sessions.rotate(raw_token, ttl=timedelta(hours=1))
    assert rotated is not None
    new_token, _new_session = rotated

    assert sessions.lookup(raw_token).revoked is True
    assert sessions.lookup(new_token).revoked is False


# --- CSRF ------------------------------------------------------------------


def test_csrf_validation_rejects_missing_or_mismatched_token():
    with pytest.raises(CsrfValidationError):
        validate_csrf(session_csrf_token="abc123", provided_token=None)
    with pytest.raises(CsrfValidationError):
        validate_csrf(session_csrf_token="abc123", provided_token="wrong-token")


def test_csrf_validation_accepts_the_matching_token():
    validate_csrf(session_csrf_token="abc123", provided_token="abc123")  # must not raise


# --- Rechteüberschreitung (privilege escalation) --------------------------


async def test_session_actor_cannot_exceed_its_granted_permissions(rig):
    service, _uow, _audit, _sessions, _rl = rig
    _token, actor = await service.login(user_id="user-1", password="correct horse battery staple", device_label="d")

    require_permission(actor, "rooms:read")  # granted - fine
    with pytest.raises(AuthorizationError):
        require_permission(actor, "emergency:manage")  # never granted to this role


def test_wildcard_permission_is_never_allowed_no_customer_root():
    with pytest.raises(WildcardPermissionError):
        Actor(user_id="user-1", household_id="hh-1", permissions=frozenset({"*"}))
