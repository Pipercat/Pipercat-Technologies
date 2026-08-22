"""Protected customer-admin area with automatic re-locking (S1V2-02-010).

DEC-121/-122: everyday device control opens by default without re-prompting
for the SystemONE password; administrative settings need fresh
re-authentication (password or a verified biometric assertion); the admin
area locks again on app backgrounding/leaving or ~5 minutes of inactivity;
this protection can never be turned off.

Deliberately a *second*, separate unlock state layered on top of a normal
session (app/auth/sessions.py) - a valid session is necessary but not
sufficient for admin actions. The lock state lives entirely server-side,
so a client cannot simply claim "I am unlocked": only a verified
unlock_admin_area() call (real password check or a verified biometric
assertion) can set it, and only server-tracked timeouts/explicit locks can
clear it.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.audit import AuditRecorder
from app.uow import UnitOfWork

from .password_hashing import verify_password
from .sessions import SessionStore

DEFAULT_ADMIN_INACTIVITY_TIMEOUT = timedelta(minutes=5)


class BiometricVerifier(Protocol):
    async def verify(self, *, user_id: str, assertion: str) -> bool:
        """Verifies a platform biometric assertion server-side (e.g. a
        WebAuthn/passkey assertion). A raw client-supplied boolean is
        deliberately never accepted as proof - see FakeBiometricVerifier
        for the shape a real implementation must fulfil."""
        ...


class FakeBiometricVerifier:
    """Dev/test stand-in. A real implementation verifies a signed platform
    assertion (S1V2-02-012 wires the real biometric flow); this only
    proves the admin-area guard correctly depends on *some* verifier
    rather than trusting the client directly."""

    def __init__(self) -> None:
        self._valid_assertions: dict[str, str] = {}  # assertion -> user_id

    def register_valid_assertion(self, assertion: str, *, user_id: str) -> None:
        self._valid_assertions[assertion] = user_id

    async def verify(self, *, user_id: str, assertion: str) -> bool:
        return self._valid_assertions.get(assertion) == user_id


class AdminAreaLockedError(PermissionError):
    def __init__(self) -> None:
        super().__init__("Admin area is locked; call unlock_admin_area() with fresh credentials first.")


class StepUpAuthenticationError(PermissionError):
    def __init__(self) -> None:
        super().__init__("Re-authentication failed; admin area was not unlocked.")


class _AdminAreaLockState:
    """Server-side-only unlock tracking, keyed by session token hash so a
    client cannot forge or extend it by sending arbitrary data."""

    def __init__(self, inactivity_timeout: timedelta) -> None:
        self._inactivity_timeout = inactivity_timeout
        self._last_activity: dict[str, datetime] = {}

    def unlock(self, session_key: str, *, now: datetime | None = None) -> None:
        self._last_activity[session_key] = now or datetime.now(UTC)

    def touch(self, session_key: str, *, now: datetime | None = None) -> None:
        if session_key in self._last_activity:
            self._last_activity[session_key] = now or datetime.now(UTC)

    def is_unlocked(self, session_key: str, *, now: datetime | None = None) -> bool:
        last = self._last_activity.get(session_key)
        if last is None:
            return False
        current = now or datetime.now(UTC)
        return (current - last) < self._inactivity_timeout

    def lock(self, session_key: str) -> None:
        self._last_activity.pop(session_key, None)


class AdminAreaService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        sessions: SessionStore,
        audit: AuditRecorder,
        biometric_verifier: BiometricVerifier,
        inactivity_timeout: timedelta = DEFAULT_ADMIN_INACTIVITY_TIMEOUT,
    ) -> None:
        self._uow_factory = uow_factory
        self._sessions = sessions
        self._audit = audit
        self._biometric_verifier = biometric_verifier
        self._lock_state = _AdminAreaLockState(inactivity_timeout)

    async def unlock_admin_area(
        self,
        raw_token: str,
        *,
        password: str | None = None,
        biometric_assertion: str | None = None,
        now: datetime | None = None,
    ) -> None:
        session = self._require_valid_session(raw_token)

        verified = False
        if password is not None:
            with self._uow_factory() as uow:
                user = uow.users.get_by_id(session.user_id)
            verified = bool(user and user.password_hash and verify_password(password, user.password_hash))
        elif biometric_assertion is not None:
            verified = await self._biometric_verifier.verify(user_id=session.user_id, assertion=biometric_assertion)

        if not verified:
            self._audit.record(
                actor=None,
                action="admin_area.stepup_failed",
                target_type="user",
                target_id=session.user_id,
                outcome="failure",
            )
            raise StepUpAuthenticationError()

        self._lock_state.unlock(_session_key(raw_token), now=now)
        self._audit.record(
            actor=None,
            action="admin_area.unlocked",
            target_type="user",
            target_id=session.user_id,
            outcome="success",
            metadata={"method": "password" if password is not None else "biometric"},
        )

    def require_unlocked(self, raw_token: str, *, now: datetime | None = None) -> None:
        """The enforcement point every admin-settings use case must call.
        No parameter or configuration exists to bypass this - "Schutz darf
        nicht deaktiviert werden" is satisfied by there being no such
        knob, not by a default."""
        session = self._require_valid_session(raw_token)
        if not self._lock_state.is_unlocked(_session_key(raw_token), now=now):
            self._audit.record(
                actor=None,
                action="admin_area.blocked_while_locked",
                target_type="user",
                target_id=session.user_id,
                outcome="failure",
            )
            raise AdminAreaLockedError()
        # Continued admin-area activity extends the inactivity window -
        # only while already unlocked; it can never *establish* an unlock.
        self._lock_state.touch(_session_key(raw_token), now=now)

    def lock(self, raw_token: str, *, reason: str) -> None:
        """Called by the client on app background/leaving the admin area,
        or internally once the inactivity timeout elapses (checked via
        require_unlocked / is_unlocked - there is no background timer
        thread; the state is evaluated lazily against the current time on
        each check, matching the pattern used throughout this codebase)."""
        session = self._sessions.lookup(raw_token)
        self._lock_state.lock(_session_key(raw_token))
        if session is not None:
            self._audit.record(
                actor=None,
                action="admin_area.locked",
                target_type="user",
                target_id=session.user_id,
                outcome="success",
                metadata={"reason": reason},
            )

    def is_unlocked(self, raw_token: str, *, now: datetime | None = None) -> bool:
        return self._lock_state.is_unlocked(_session_key(raw_token), now=now)

    def _require_valid_session(self, raw_token: str):
        from .sessions import StoredSession  # local import: typing only

        session: StoredSession | None = self._sessions.lookup(raw_token)
        if session is None or session.revoked or session.is_expired():
            raise AdminAreaLockedError()
        return session


def _session_key(raw_token: str) -> str:
    # Re-use the same hashing SessionStore already applies, so the lock
    # state is keyed the same way sessions are - never by the raw token.
    import hashlib

    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
