"""Migration test required by S1V2-02-001's Definition of Done: "Leere DB
migriert reproduzierbar auf aktuellen Stand; Migrationstest vorhanden."
"""

import os

from sqlalchemy import create_engine, inspect

from tests.db_conftest import alembic_config, requires_database

pytestmark = requires_database

EXPECTED_TABLES = {
    "households",
    "rooms",
    "roles",
    "permissions",
    "role_permissions",
    "users",
    "client_devices",
    "integrations",
    "devices",
    "capabilities",
    "automations",
    "notification_preferences",
    "remote_approvals",
    "audit_events",
}


def _table_names() -> set[str]:
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_empty_database_migrates_to_head_with_all_expected_tables():
    from alembic import command

    cfg = alembic_config()
    command.downgrade(cfg, "base")  # start from a guaranteed-empty schema

    command.upgrade(cfg, "head")
    tables = _table_names()
    assert EXPECTED_TABLES <= tables


def test_migration_is_reproducible_upgrade_downgrade_upgrade():
    from alembic import command

    cfg = alembic_config()

    command.upgrade(cfg, "head")
    first_pass = _table_names()

    command.downgrade(cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(_table_names())

    command.upgrade(cfg, "head")
    second_pass = _table_names()

    assert first_pass == second_pass


def test_downgrade_from_head_removes_every_application_table():
    from alembic import command

    cfg = alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    remaining = _table_names()
    assert EXPECTED_TABLES.isdisjoint(remaining)
    # alembic_version itself is allowed to remain (empty of revision rows).
    assert remaining <= {"alembic_version"}
