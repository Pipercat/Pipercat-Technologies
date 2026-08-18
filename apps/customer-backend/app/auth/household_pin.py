"""Household PIN with escalating lockout ("Sperrstaffel") and admin reset
(S1V2-02-010, wired up here for the reset step).

DEC-123-125, DEC-129: a separate 4-8 digit household PIN; the customer
admin decides per user whether a PIN exists; after ~5 failed attempts the
first lockout kicks in, then progressively longer lockouts; the lockout
can only be cleared by an admin who has *themselves* freshly
re-authenticated (S1V2-02-010's admin-area unlock, not just anyone with
users:manage); the PIN itself is never stored in plaintext or in any
reversible form.
"""

import re
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.audit import AuditRecorder
from app.authorization import Actor, CrossHouseholdAccessError, require_permission
from app.uow import UnitOfWork

from .admin_area import AdminAreaService
from .password_hashing import hash_password, verify_password

PIN_PATTERN = re.compile(r"^\d{4,8}$")

LOCKOUT_THRESHOLD = 5
# Sperrstaffel: each time the threshold is hit again, the *next* stage's
# duration applies - staying at the last stage if exhausted, never
# shrinking back down or unlocking early.
LOCKOUT_STAGES: list[timedelta] = [
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=24),
]


class InvalidPinFormatError(ValueError):
    def __init__(self) -> None:
        super().__init__("PIN must be 4-8 digits.")


class PinNotEnabledError(PermissionError):
    """"Fehlendes Benutzerrecht": this user has no household PIN configured
    - a customer admin must enable one first."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"User '{user_id}' does not have a household PIN enabled.")
        self.user_id = user_id


class PinLockedError(PermissionError):
    def __init__(self, retry_after: timedelta) -> None:
        super().__init__(f"PIN entry is locked for another {retry_after}.")
        self.retry_after = retry_after


class InvalidPinError(ValueError):
    pass


class _PinLockoutTracker:
    """Server-side-only, per-user. A client cannot reset this by retrying
    - only time passing (self-service) or an admin-verified reset
    (HouseholdPinService.reset_lockout) clears it."""

    def __init__(self, threshold: int, stages: list[timedelta]) -> None:
        self._threshold = threshold
        self._stages = stages
        self._failures: dict[str, int] = defaultdict(int)
        self._stage: dict[str, int] = defaultdict(int)
        self._locked_until: dict[str, datetime] = {}

    def is_locked(self, user_id: str, *, now: datetime | None = None) -> timedelta | None:
        until = self._locked_until.get(user_id)
        if until is None:
            return None
        current = now or datetime.now(UTC)
        if current >= until:
            return None
        return until - current

    def record_failure(self, user_id: str, *, now: datetime | None = None) -> None:
        self._failures[user_id] += 1
        if self._failures[user_id] >= self._threshold:
            current = now or datetime.now(UTC)
            stage_index = min(self._stage[user_id], len(self._stages) - 1)
            self._locked_until[user_id] = current + self._stages[stage_index]
            self._stage[user_id] = min(self._stage[user_id] + 1, len(self._stages) - 1)
            self._failures[user_id] = 0

    def record_success(self, user_id: str) -> None:
        self._failures[user_id] = 0
        self._stage[user_id] = 0
        self._locked_until.pop(user_id, None)

    def reset(self, user_id: str) -> None:
        self._failures[user_id] = 0
        self._stage[user_id] = 0
        self._locked_until.pop(user_id, None)


class HouseholdPinService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        audit: AuditRecorder,
        admin_area: AdminAreaService,
        lockout_threshold: int = LOCKOUT_THRESHOLD,
        lockout_stages: list[timedelta] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._audit = audit
        self._admin_area = admin_area
        self._lockout = _PinLockoutTracker(lockout_threshold, lockout_stages or LOCKOUT_STAGES)

    def _require_target_in_same_household(self, admin_actor: Actor, uow: UnitOfWork, target_user_id: str) -> None:
        """"Kundenadmin entscheidet pro Benutzer" - but only for users in
        the admin's own household. users:manage grants the kind of
        action, not authority over an arbitrary target_user_id."""
        target_user = uow.users.get_by_id(target_user_id)
        if target_user is not None and target_user.household_id != admin_actor.household_id:
            self._audit.record(
                actor=admin_actor,
                action="pin.blocked",
                target_type="user",
                target_id=target_user_id,
                outcome="failure",
                metadata={"reason": "cross_household"},
            )
            raise CrossHouseholdAccessError()

    async def enable_pin(self, admin_actor: Actor, *, target_user_id: str, pin: str) -> None:
        """"Kundenadmin entscheidet pro Benutzer" - only an admin acting on
        someone else's account configures a PIN, never a bare user-side
        self-service call."""
        require_permission(admin_actor, "users:manage")
        if not PIN_PATTERN.match(pin):
            raise InvalidPinFormatError()

        with self._uow_factory() as uow:
            self._require_target_in_same_household(admin_actor, uow, target_user_id)
            uow.users.set_pin_hash(target_user_id, hash_password(pin))
            uow.commit()
        self._lockout.reset(target_user_id)
        self._audit.record(
            actor=admin_actor, action="pin.enabled", target_type="user", target_id=target_user_id, outcome="success"
        )

    async def disable_pin(self, admin_actor: Actor, *, target_user_id: str) -> None:
        require_permission(admin_actor, "users:manage")
        with self._uow_factory() as uow:
            self._require_target_in_same_household(admin_actor, uow, target_user_id)
            uow.users.set_pin_hash(target_user_id, None)
            uow.commit()
        self._lockout.reset(target_user_id)
        self._audit.record(
            actor=admin_actor, action="pin.disabled", target_type="user", target_id=target_user_id, outcome="success"
        )

    async def verify_pin(self, user_id: str, pin: str, *, now: datetime | None = None) -> None:
        remaining = self._lockout.is_locked(user_id, now=now)
        if remaining is not None:
            self._audit.record(
                actor=None, action="pin.attempt_while_locked", target_type="user", target_id=user_id, outcome="failure"
            )
            raise PinLockedError(remaining)

        with self._uow_factory() as uow:
            user = uow.users.get_by_id(user_id)

        if user is None or user.pin_hash is None:
            raise PinNotEnabledError(user_id)

        if not verify_password(pin, user.pin_hash):
            self._lockout.record_failure(user_id, now=now)
            locked_now = self._lockout.is_locked(user_id, now=now)
            self._audit.record(
                actor=None,
                action="pin.verify_failed",
                target_type="user",
                target_id=user_id,
                outcome="failure",
                metadata={"nowLocked": locked_now is not None},
            )
            raise InvalidPinError()

        self._lockout.record_success(user_id)
        self._audit.record(actor=None, action="pin.verified", target_type="user", target_id=user_id, outcome="success")

    async def reset_lockout(self, admin_actor: Actor, admin_raw_token: str, *, target_user_id: str) -> None:
        """"Reset des Sperrstatus nur nach erneuter Adminauthentifizierung":
        the admin's *own* admin-area must currently be unlocked (a fresh
        S1V2-02-010 step-up), not merely holding the users:manage
        permission - a stale/ambient session is not enough to clear
        someone else's lockout."""
        require_permission(admin_actor, "users:manage")
        self._admin_area.require_unlocked(admin_raw_token)
        with self._uow_factory() as uow:
            self._require_target_in_same_household(admin_actor, uow, target_user_id)

        self._lockout.reset(target_user_id)
        self._audit.record(
            actor=admin_actor,
            action="pin.lockout_reset",
            target_type="user",
            target_id=target_user_id,
            outcome="success",
        )

    def is_locked(self, user_id: str, *, now: datetime | None = None) -> timedelta | None:
        return self._lockout.is_locked(user_id, now=now)
