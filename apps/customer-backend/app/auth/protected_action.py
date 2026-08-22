"""Fresh, non-cached authorization for protected per-action operations
(camera, door lock, comparable) - S1V2-02-012.

DEC-127-129: unlike the admin area (S1V2-02-010, a timed unlock window
that stays valid for ~5 minutes across many actions), there is
deliberately *no* unlock session here - "keine PIN-Freischaltsession".
Every single protected action calls authorize_action() immediately
before it runs, and nothing about a prior successful call is cached or
reused: a second action always needs its own fresh PIN entry or
biometric assertion, even if it follows the first by a second.

Biometric verification, where the customer admin has allowed it for a
user, only ever replaces *how* that user proves themselves for one
action ("Biometrie ersetzt nur Eingabe, nie Berechtigungsprüfung") - the
underlying require_permission() authorization check always still runs
regardless of which entry method was used, so a successful biometric
assertion from a user who lacks the permission is still rejected.
"""

from collections.abc import Callable

from app.audit import AuditRecorder
from app.authorization import Actor, CrossHouseholdAccessError, require_permission
from app.uow import UnitOfWork

from .admin_area import BiometricVerifier
from .household_pin import HouseholdPinService


class NoCredentialSuppliedError(ValueError):
    def __init__(self) -> None:
        super().__init__("A protected action requires either a PIN or a biometric assertion.")


class BiometricNotAllowedError(PermissionError):
    """The customer admin has not (yet) allowed this user to substitute
    biometrics for PIN entry on protected actions - biometrics are opt-in
    per user, decided by an admin, never a self-service default."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"Biometric entry is not allowed for user '{user_id}'.")
        self.user_id = user_id


class BiometricVerificationFailedError(PermissionError):
    def __init__(self) -> None:
        super().__init__("Biometric assertion could not be verified.")


class ProtectedActionGuard:
    """The enforcement point every camera-/door-lock-/comparable use case
    must call immediately before acting. There is no unlock state to
    check first and no unlock state to set afterwards - each call is
    entirely self-contained, which is what guarantees two consecutive
    actions each require their own fresh authorization."""

    def __init__(
        self,
        pin_service: HouseholdPinService,
        audit: AuditRecorder,
        biometric_verifier: BiometricVerifier,
        uow_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._pin_service = pin_service
        self._audit = audit
        self._biometric_verifier = biometric_verifier
        self._uow_factory = uow_factory
        # "Kundenadmin darf lokale Biometrie erlauben" - a persistent,
        # admin-controlled per-user decision. (Scoped to the user rather
        # than a specific paired client device: device pairing/
        # registration is not yet an implemented feature - see
        # docs/architecture/protected-actions.md "Bewusst nicht Teil
        # dieser Aufgabe".)
        self._biometric_allowed: set[str] = set()

    def _require_target_in_same_household(self, actor: Actor, target_user_id: str, *, action: str) -> None:
        """Datenisolation (S1V2-02-015): a permission grant like
        users:manage or a protected-action permission authorizes the
        *kind* of action, never an arbitrary target_user_id outside the
        actor's own household."""
        with self._uow_factory() as uow:
            target_user = uow.users.get_by_id(target_user_id)
        if target_user is not None and target_user.household_id != actor.household_id:
            self._audit.record(
                actor=actor,
                action="protected_action.denied",
                target_type="user",
                target_id=target_user_id,
                outcome="failure",
                metadata={"action": action, "reason": "cross_household"},
            )
            raise CrossHouseholdAccessError()

    def allow_biometric(self, admin_actor: Actor, *, target_user_id: str) -> None:
        require_permission(admin_actor, "users:manage")
        self._require_target_in_same_household(admin_actor, target_user_id, action="biometric_allowed")
        self._biometric_allowed.add(target_user_id)
        self._audit.record(
            actor=admin_actor,
            action="protected_action.biometric_allowed",
            target_type="user",
            target_id=target_user_id,
            outcome="success",
        )

    def disallow_biometric(self, admin_actor: Actor, *, target_user_id: str) -> None:
        require_permission(admin_actor, "users:manage")
        self._require_target_in_same_household(admin_actor, target_user_id, action="biometric_disallowed")
        self._biometric_allowed.discard(target_user_id)
        self._audit.record(
            actor=admin_actor,
            action="protected_action.biometric_disallowed",
            target_type="user",
            target_id=target_user_id,
            outcome="success",
        )

    def is_biometric_allowed(self, user_id: str) -> bool:
        return user_id in self._biometric_allowed

    async def authorize_action(
        self,
        actor: Actor,
        *,
        target_user_id: str,
        permission: str,
        action: str,
        pin: str | None = None,
        biometric_assertion: str | None = None,
    ) -> None:
        """Must be called freshly before every single protected action -
        never once up front to cover several actions. Raises on any
        failure; returns None on success. `action` is a free-form label
        (e.g. "camera.view", "lock.unlock") recorded for audit only."""
        require_permission(actor, permission)
        self._require_target_in_same_household(actor, target_user_id, action=action)

        if biometric_assertion is not None:
            if target_user_id not in self._biometric_allowed:
                self._audit.record(
                    actor=actor,
                    action="protected_action.denied",
                    target_type="user",
                    target_id=target_user_id,
                    outcome="failure",
                    metadata={"action": action, "reason": "biometric_not_allowed"},
                )
                raise BiometricNotAllowedError(target_user_id)

            verified = await self._biometric_verifier.verify(user_id=target_user_id, assertion=biometric_assertion)
            if not verified:
                self._audit.record(
                    actor=actor,
                    action="protected_action.denied",
                    target_type="user",
                    target_id=target_user_id,
                    outcome="failure",
                    metadata={"action": action, "reason": "biometric_verification_failed"},
                )
                raise BiometricVerificationFailedError()

            self._audit.record(
                actor=actor,
                action="protected_action.authorized",
                target_type="user",
                target_id=target_user_id,
                outcome="success",
                metadata={"action": action, "method": "biometric"},
            )
            return

        if pin is not None:
            # HouseholdPinService.verify_pin() already audits its own
            # success/failure and enforces the Sperrstaffel; it has no
            # unlock-session concept of its own either, which is exactly
            # what lets us reuse it here without introducing one.
            await self._pin_service.verify_pin(target_user_id, pin)
            self._audit.record(
                actor=actor,
                action="protected_action.authorized",
                target_type="user",
                target_id=target_user_id,
                outcome="success",
                metadata={"action": action, "method": "pin"},
            )
            return

        raise NoCredentialSuppliedError()
