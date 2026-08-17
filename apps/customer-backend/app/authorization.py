"""Authorization at the use-case boundary (S1V2-02-003, sessions wired up in
S1V2-02-008): "Autorisierung an Use-Case-Grenzen, nicht nur UI/API-Router" -
every service method that changes state or reads sensitive data calls
require_permission() itself. An API route being reachable is not
authorization; the use case enforces it independently.
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
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        if "*" in self.permissions:
            raise WildcardPermissionError()


class AuthorizationError(PermissionError):
    def __init__(self, permission: str) -> None:
        super().__init__(f"Missing required permission '{permission}'")
        self.permission = permission


def require_permission(actor: Actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise AuthorizationError(permission)
