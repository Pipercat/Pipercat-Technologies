"""Authorization at the use-case boundary (S1V2-02-003, sessions wired up in
S1V2-02-008): "Autorisierung an Use-Case-Grenzen, nicht nur UI/API-Router" -
every service method that changes state or reads sensitive data calls
require_permission() itself. An API route being reachable is not
authorization; the use case enforces it independently.

household_id/require_same_household (S1V2-02-015): "Kein Kunden-Root"
(S1V2-02-008) and per-role RBAC alone are not data isolation - RBAC only
answers "is this actor allowed to do this kind of thing at all", never
"is this specific target resource actually theirs". Without a household
check, an admin actor holding a broad permission like users:manage could
supply any target_user_id/target_household_id and have it accepted, not
just ones belonging to their own household. Every use case that accepts
a caller-supplied household_id, or resolves one from a target resource,
must call require_same_household() in addition to require_permission().
"""

from dataclasses import dataclass


class WildcardPermissionError(ValueError):
    """"Kein Kunden-Root" (S1V2-02-008): no Actor may ever hold a wildcard
    permission that bypasses individual checks - every grant must be an
    enumerable, specific permission string. Enforced here, not just by
    convention, so a future role definition cannot silently introduce one."""

    def __init__(self) -> None:
        super().__init__("Wildcard permissions ('*') are not allowed - grant specific permissions instead.")


@dataclass(frozen=True)
class Actor:
    user_id: str
    household_id: str
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        if "*" in self.permissions:
            raise WildcardPermissionError()


class AuthorizationError(PermissionError):
    def __init__(self, permission: str) -> None:
        super().__init__(f"Missing required permission '{permission}'")
        self.permission = permission


class CrossHouseholdAccessError(PermissionError):
    """Raised when an actor's own household does not match the household
    a targeted resource actually belongs to - independent of whether the
    actor holds the relevant permission in general."""

    def __init__(self) -> None:
        super().__init__("Actor's household does not match the target resource's household.")


def require_permission(actor: Actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise AuthorizationError(permission)


def require_same_household(actor: Actor, resource_household_id: str) -> None:
    if actor.household_id != resource_household_id:
        raise CrossHouseholdAccessError()
