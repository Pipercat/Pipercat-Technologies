"""Authorization at the use-case boundary (S1V2-02-003):
"Autorisierung an Use-Case-Grenzen, nicht nur UI/API-Router" - every
service method that changes state or reads sensitive data calls
require_permission() itself. An API route being reachable is not
authorization; the use case enforces it independently.

Full role/permission persistence and session-derived Actors land with
S1V2-02-008/-009. For now, Actor is a plain, framework-agnostic value the
caller constructs from whatever auth context exists at the time.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    user_id: str
    permissions: frozenset[str]


class AuthorizationError(PermissionError):
    def __init__(self, permission: str) -> None:
        super().__init__(f"Missing required permission '{permission}'")
        self.permission = permission


def require_permission(actor: Actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise AuthorizationError(permission)
