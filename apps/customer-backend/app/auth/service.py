"""AuthenticationService (S1V2-02-008): ties password hashing, the
session store, rate limiting and audit together. Reuses the UnitOfWork/
Repository pattern from S1V2-02-003 for the User lookup.
"""

from collections.abc import Callable
from datetime import timedelta

from app.audit import AuditRecorder
from app.authorization import Actor
from app.uow import UnitOfWork

from .password_hashing import verify_password
from .rate_limiter import RateLimiter
from .sessions import SessionStore

DEFAULT_SESSION_TTL = timedelta(hours=12)
DEFAULT_LOGIN_RATE_LIMIT = 5
DEFAULT_LOGIN_RATE_WINDOW_SECONDS = 60.0


class InvalidCredentialsError(Exception):
    pass


class SessionExpiredError(Exception):
    pass


class SessionRevokedError(Exception):
    pass


class UnknownSessionError(Exception):
    pass


class RateLimitExceededError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"Too many attempts for '{key}'; try again later.")
        self.key = key


class AuthenticationService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        sessions: SessionStore,
        audit: AuditRecorder,
        rate_limiter: RateLimiter | None = None,
        session_ttl: timedelta = DEFAULT_SESSION_TTL,
    ) -> None:
        self._uow_factory = uow_factory
        self._sessions = sessions
        self._audit = audit
        self._rate_limiter = rate_limiter or RateLimiter(
            DEFAULT_LOGIN_RATE_LIMIT, DEFAULT_LOGIN_RATE_WINDOW_SECONDS
        )
        self._session_ttl = session_ttl

    async def login(self, *, user_id: str, password: str, device_label: str) -> tuple[str, Actor]:
        rate_key = f"login:{user_id}"
        if not self._rate_limiter.allow(rate_key):
            self._audit.record(
                actor=None, action="auth.login_rate_limited", target_type="user", target_id=user_id, outcome="failure"
            )
            raise RateLimitExceededError(rate_key)

        with self._uow_factory() as uow:
            user = uow.users.get_by_id(user_id)
            permissions = uow.users.get_permissions_for_role(user.role_id) if user else frozenset()

        if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
            self._audit.record(
                actor=None, action="auth.login_failed", target_type="user", target_id=user_id, outcome="failure"
            )
            raise InvalidCredentialsError("Invalid user id or password.")

        self._rate_limiter.reset(rate_key)
        actor = Actor(user_id=user.id, household_id=user.household_id, permissions=permissions)
        raw_token, _session = self._sessions.create(
            user_id=user.id,
            household_id=user.household_id,
            permissions=permissions,
            device_label=device_label,
            ttl=self._session_ttl,
        )
        self._audit.record(
            actor=actor, action="auth.login_succeeded", target_type="user", target_id=user.id, outcome="success"
        )
        return raw_token, actor

    async def authenticate(self, raw_token: str) -> Actor:
        session = self._sessions.lookup(raw_token)
        if session is None:
            raise UnknownSessionError("Session token is not recognized.")
        if session.revoked:
            self._audit.record(
                actor=None,
                action="auth.session_use_after_revocation",
                target_type="user",
                target_id=session.user_id,
                outcome="failure",
            )
            raise SessionRevokedError("This session has been revoked.")
        if session.is_expired():
            self._audit.record(
                actor=None,
                action="auth.session_use_after_expiry",
                target_type="user",
                target_id=session.user_id,
                outcome="failure",
            )
            raise SessionExpiredError("This session has expired.")
        return Actor(user_id=session.user_id, household_id=session.household_id, permissions=session.permissions)

    async def logout(self, raw_token: str) -> None:
        session = self._sessions.lookup(raw_token)
        revoked = self._sessions.revoke(raw_token)
        if revoked:
            self._audit.record(
                actor=(
                    Actor(user_id=session.user_id, household_id=session.household_id, permissions=frozenset())
                    if session
                    else None
                ),
                action="auth.logout",
                target_type="user",
                target_id=session.user_id if session else None,
                outcome="success",
            )
