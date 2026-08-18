"""Role catalog and role-assignment guard (S1V2-02-009).

DEC-119/-120: a customer admin manages their own users/rooms/customer-side
roles; system/service/root/Pipercat roles stay protected; the service role
is least-privilege; full root rights are never a customer feature;
authorization happens server-side.
"""

from collections.abc import Callable

from .audit import AuditRecorder
from .authorization import Actor, require_permission
from .uow import UnitOfWork

# Customer-facing roles - what a customer admin may assign to a household
# member. Matches the role set already proven in the existing Node.js
# pilot (mvp/systemone-pi/lib/local-sessions.js) for continuity.
CUSTOMER_ROLE_KEYS: frozenset[str] = frozenset({"owner", "administrator", "member", "guest", "display"})

# Never assignable through RoleManagementService, regardless of the
# caller's own permissions - checked in code (see assign_role), not just
# documented. "system"/"service" back internal/automated processes;
# "root" is a theoretical maximal-privilege role that exists conceptually
# for break-glass internal tooling outside this service, never a customer
# feature; "pipercat_support" is Pipercat's own remote-support identity,
# gated entirely outside the customer role system (S1V2-05-*).
PROTECTED_ROLE_KEYS: frozenset[str] = frozenset({"system", "service", "root", "pipercat_support"})

# Every permission set is finite and enumerable - no role, including
# "root", ever holds a wildcard (app/authorization.py::Actor enforces this
# structurally too).
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset(
        {
            "rooms:read",
            "rooms:manage",
            "devices:read",
            "devices:manage",
            "devices:control",
            "automations:read",
            "automations:manage",
            "users:manage",
            "emergency:manage",
            "backup:manage",
            "updates:approve",
            "integrations:manage",
        }
    ),
    "administrator": frozenset(
        {
            "rooms:read",
            "rooms:manage",
            "devices:read",
            "devices:manage",
            "devices:control",
            "automations:read",
            "automations:manage",
            "users:manage",
            "emergency:manage",
            "integrations:manage",
        }
    ),
    "member": frozenset({"rooms:read", "devices:read", "devices:control", "automations:read"}),
    "guest": frozenset({"rooms:read", "devices:read"}),
    "display": frozenset({"rooms:read"}),
    # Protected roles below. "service" is deliberately the smallest set of
    # any role in this catalog (least-privilege service role).
    "service": frozenset({"system:health:read", "system:metrics:read"}),
    "system": frozenset({"system:health:read", "system:metrics:read", "system:selfheal:execute"}),
    "pipercat_support": frozenset({"system:health:read", "system:metrics:read"}),
    "root": frozenset(
        {
            "rooms:read",
            "rooms:manage",
            "devices:read",
            "devices:manage",
            "devices:control",
            "automations:read",
            "automations:manage",
            "users:manage",
            "emergency:manage",
            "backup:manage",
            "updates:approve",
            "integrations:manage",
            "system:health:read",
            "system:metrics:read",
            "system:selfheal:execute",
            "system:root_override",
        }
    ),
}


class ProtectedRoleError(PermissionError):
    def __init__(self, role_key: str) -> None:
        super().__init__(
            f"Role '{role_key}' is protected (system/service/root/Pipercat) and can never be "
            "assigned through the customer role-management service."
        )
        self.role_key = role_key


class UnknownRoleError(ValueError):
    def __init__(self, role_key: str) -> None:
        super().__init__(f"Role '{role_key}' does not exist in the role catalog.")
        self.role_key = role_key


class RoleManagementService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], audit: AuditRecorder) -> None:
        self._uow_factory = uow_factory
        self._audit = audit

    def list_assignable_roles(self, actor: Actor) -> frozenset[str]:
        """Only ever returns the customer-facing set - a protected role is
        never even listed as an option, let alone assignable."""
        require_permission(actor, "users:manage")
        return CUSTOMER_ROLE_KEYS

    async def assign_role(self, actor: Actor, *, target_user_id: str, role_key: str) -> None:
        # 1. Normal authorization first...
        require_permission(actor, "users:manage")

        # 2. ...then the protected-role guard as defense in depth: even an
        # actor who legitimately holds "users:manage" (e.g. a compromised
        # or malicious owner/administrator account, or a client sending a
        # hand-crafted request naming an unexpected role) can never assign
        # a protected role through this path. This check does not trust
        # the caller's permission set as sufficient by itself.
        if role_key in PROTECTED_ROLE_KEYS:
            self._audit.record(
                actor=actor,
                action="roles.assignment_blocked",
                target_type="user",
                target_id=target_user_id,
                outcome="failure",
                metadata={"attemptedRole": role_key, "reason": "protected_role"},
            )
            raise ProtectedRoleError(role_key)

        if role_key not in ROLE_PERMISSIONS:
            self._audit.record(
                actor=actor,
                action="roles.assignment_blocked",
                target_type="user",
                target_id=target_user_id,
                outcome="failure",
                metadata={"attemptedRole": role_key, "reason": "unknown_role"},
            )
            raise UnknownRoleError(role_key)

        with self._uow_factory() as uow:
            role_id = uow.roles.get_id_by_key(role_key)
            if role_id is None:
                raise UnknownRoleError(role_key)
            uow.users.set_role(target_user_id, role_id)
            uow.commit()

        self._audit.record(
            actor=actor,
            action="roles.assigned",
            target_type="user",
            target_id=target_user_id,
            outcome="success",
            metadata={"role": role_key},
        )
