"""Structural tests for the S1V2-02-001 schema against a real PostgreSQL
database (via the migrated_db fixture, which upgrades to head before each
test and tears the schema down after)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.audit import GENESIS_HASH
from app.db.models import AuditEvent, Capability, Device, Household, Integration, RemoteApproval, Room, Role, User
from tests.db_conftest import migrated_db, requires_database  # noqa: F401 - fixture import

pytestmark = requires_database


def _household(session, product_class="pi"):
    household = Household(name="Test Household", product_class=product_class)
    session.add(household)
    session.commit()
    return household


@pytest.mark.security
def test_no_plaintext_password_or_pin_columns_exist():
    column_names = {c.name for c in User.__table__.columns}
    assert "password" not in column_names
    assert "pin" not in column_names
    assert {"password_hash", "pin_hash"} <= column_names


def test_invalid_product_class_is_rejected_by_check_constraint(migrated_db):
    session = migrated_db
    session.add(Household(name="Bad", product_class="toaster"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_household_room_device_cascade(migrated_db):
    session = migrated_db
    household = _household(session)
    # "owner" is seeded by alembic/versions/0005_seed_role_catalog.py
    # (S1V2-02-028) - look it up rather than creating a duplicate, which
    # would violate roles.key's uniqueness constraint.
    role = session.scalars(select(Role).where(Role.key == "owner")).one()

    room = Room(household_id=household.id, name="Living Room")
    session.add(room)
    integration = Integration(household_id=household.id, type="home_assistant")
    session.add(integration)
    session.commit()

    device = Device(
        household_id=household.id,
        room_id=room.id,
        integration_id=integration.id,
        external_id="light.living_room_lamp",
        name="Living Room Lamp",
        device_type="light",
    )
    session.add(device)
    session.commit()

    session.add(Capability(device_id=device.id, key="on_off", value_type="boolean"))
    session.commit()

    # Deleting the household must cascade to room/integration/device/capability.
    session.delete(household)
    session.commit()
    # session.get() checks the identity map before the DB; without clearing
    # it, it would either return the stale in-memory Room/Device objects, or
    # (with only expire_all()) raise ObjectDeletedError instead of treating
    # a cascade-deleted row as simply "not found". expunge_all() forces a
    # clean DB read, which is what we actually want to assert on here.
    session.expunge_all()

    assert session.get(Room, room.id) is None
    assert session.get(Device, device.id) is None


def test_duplicate_external_id_within_same_integration_is_rejected(migrated_db):
    session = migrated_db
    household = _household(session)
    integration = Integration(household_id=household.id, type="home_assistant")
    session.add(integration)
    session.commit()

    session.add(
        Device(
            household_id=household.id,
            integration_id=integration.id,
            external_id="light.duplicate",
            name="A",
            device_type="light",
        )
    )
    session.commit()

    session.add(
        Device(
            household_id=household.id,
            integration_id=integration.id,
            external_id="light.duplicate",
            name="B",
            device_type="light",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_audit_event_survives_household_deletion_with_null_reference(migrated_db):
    """Audit events must never be silently lost just because the household
    they reference was removed (S1V2-02-001: audit events are separate from
    mutable fact records)."""
    session = migrated_db
    household = _household(session)

    event = AuditEvent(
        household_id=household.id,
        action="household.created",
        target_type="household",
        target_id=household.id,
        outcome="success",
        sequence_number=1,
        previous_hash=GENESIS_HASH,
        record_hash="0" * 64,  # not verified here - see test_audit.py for chain-integrity tests
    )
    session.add(event)
    session.commit()
    event_id = event.id

    session.delete(household)
    session.commit()
    session.expunge_all()  # see comment in test_household_room_device_cascade

    surviving = session.get(AuditEvent, event_id)
    assert surviving is not None
    assert surviving.household_id is None  # FK ON DELETE SET NULL, row itself untouched


def test_invalid_audit_event_outcome_is_rejected(migrated_db):
    session = migrated_db
    session.add(
        AuditEvent(
            action="x",
            target_type="y",
            outcome="maybe",
            sequence_number=1,
            previous_hash=GENESIS_HASH,
            record_hash="0" * 64,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_remote_approval_status_check_constraint(migrated_db):
    session = migrated_db
    household = _household(session)
    now = datetime.now(UTC)
    session.add(
        RemoteApproval(
            household_id=household.id,
            requested_by="support-tool",
            status="not-a-real-status",
            requested_at=now,
            expires_at=now + timedelta(minutes=10),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
