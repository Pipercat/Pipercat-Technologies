"""seed role catalog

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-21 17:00:00.000000

Seeds `roles`/`permissions`/`role_permissions` from the role catalog
already defined in code (`app/roles.py::ROLE_PERMISSIONS`, S1V2-02-009) -
until now nothing ever wrote that catalog into the database, so
`RoleRepository.get_id_by_key()` returned `None` for every role on a
fresh install (a pre-existing gap, discovered and fixed here while
building S1V2-02-028, which needs a real "owner" role_id to atomically
create a household's first user).

Deliberately hardcodes the role/permission data as a frozen snapshot
rather than importing `app.roles` - a migration's behavior must not
silently change if the application code it once mirrored is edited
later. IDs are deterministic (uuid5 over a fixed namespace + key) so
upgrade/downgrade/upgrade reproduces identical rows, matching
tests/test_migrations.py's round-trip check.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "systemone.pipercat.tech")


def _role_id(key: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"role:{key}")


def _permission_id(key: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"permission:{key}")


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset(
        {
            "rooms:read", "rooms:manage", "devices:read", "devices:manage", "devices:control",
            "automations:read", "automations:manage", "users:manage", "emergency:manage",
            "backup:manage", "updates:approve", "integrations:manage", "audit:read",
        }
    ),
    "administrator": frozenset(
        {
            "rooms:read", "rooms:manage", "devices:read", "devices:manage", "devices:control",
            "automations:read", "automations:manage", "users:manage", "emergency:manage",
            "integrations:manage", "audit:read",
        }
    ),
    "member": frozenset({"rooms:read", "devices:read", "devices:control", "automations:read"}),
    "guest": frozenset({"rooms:read", "devices:read"}),
    "display": frozenset({"rooms:read"}),
    "service": frozenset({"system:health:read", "system:metrics:read"}),
    "system": frozenset({"system:health:read", "system:metrics:read", "system:selfheal:execute"}),
    "pipercat_support": frozenset({"system:health:read", "system:metrics:read", "audit:read"}),
    "root": frozenset(
        {
            "rooms:read", "rooms:manage", "devices:read", "devices:manage", "devices:control",
            "automations:read", "automations:manage", "users:manage", "emergency:manage",
            "backup:manage", "updates:approve", "integrations:manage", "audit:read",
            "system:health:read", "system:metrics:read", "system:selfheal:execute", "system:root_override",
        }
    ),
}

ROLE_NAMES: dict[str, str] = {
    "owner": "Owner",
    "administrator": "Administrator",
    "member": "Member",
    "guest": "Guest",
    "display": "Display",
    "service": "Service",
    "system": "System",
    "pipercat_support": "Pipercat Support",
    "root": "Root",
}

roles_table = sa.table("roles", sa.column("id", sa.UUID()), sa.column("key", sa.String), sa.column("name", sa.String))
permissions_table = sa.table(
    "permissions", sa.column("id", sa.UUID()), sa.column("key", sa.String), sa.column("description", sa.Text)
)
role_permissions_table = sa.table(
    "role_permissions", sa.column("role_id", sa.UUID()), sa.column("permission_id", sa.UUID())
)


def upgrade() -> None:
    all_permission_keys = sorted({permission for permissions in ROLE_PERMISSIONS.values() for permission in permissions})

    op.bulk_insert(
        permissions_table,
        [{"id": _permission_id(key), "key": key, "description": ""} for key in all_permission_keys],
    )
    op.bulk_insert(
        roles_table,
        [{"id": _role_id(key), "key": key, "name": ROLE_NAMES[key]} for key in ROLE_PERMISSIONS],
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role_id": _role_id(role_key), "permission_id": _permission_id(permission_key)}
            for role_key, permissions in ROLE_PERMISSIONS.items()
            for permission_key in permissions
        ],
    )


def downgrade() -> None:
    # A plain `DELETE ... WHERE id IN (...)` on `roles` would violate
    # `users.role_id`'s FK (ondelete="RESTRICT") for any test that has
    # since created a real User against one of these seeded roles - by
    # the time this downgrade runs, `users` is still fully populated,
    # only later (earlier-numbered) migrations' downgrades actually drop
    # that table. `TRUNCATE ... CASCADE` empties `users` right along with
    # the role tables, which is harmless here: "downgrade to base" always
    # ends with every application table dropped anyway (see
    # tests/test_migrations.py), so emptying `users` a few migration
    # steps earlier than its own table-drop changes nothing observable.
    op.execute(sa.text("TRUNCATE TABLE users, role_permissions, roles, permissions RESTART IDENTITY CASCADE"))
