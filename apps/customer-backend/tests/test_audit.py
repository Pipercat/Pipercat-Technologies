"""S1V2-02-014 Definition of Done: "Tamper-Test verändert historischen
Datensatz und Integritätsprüfung erkennt dies" - proven directly below by
recording real events through SqlAlchemyAuditRecorder, then bypassing it
entirely with a raw UPDATE (exactly what an attacker with database access
would do) and showing verify_chain_integrity() catches it."""

import os

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.audit import GENESIS_HASH, AuditLogService, SqlAlchemyAuditRecorder, verify_chain_integrity
from app.authorization import Actor, AuthorizationError
from app.db.models import AuditEvent, Household, Role, User
from tests.db_conftest import migrated_db, requires_database  # noqa: F401
from tests.fakes import make_actor

pytestmark = [requires_database, pytest.mark.security]


def _session_factory():
    engine = create_engine(os.environ["DATABASE_URL"])
    return sessionmaker(bind=engine, expire_on_commit=False)


def _make_real_admin_actor(db) -> Actor:
    """audit_events.actor_user_id has a real FK to users.id - a synthetic
    make_actor() UUID (fine for permission checks alone) violates it once
    that actor is actually recorded as an AuditEvent row, as happens here
    via AuditLogService.list_events()'s self-audit."""
    household = Household(name="Test", product_class="pi")
    db.add(household)
    db.commit()
    role = Role(key="owner", name="Owner")
    db.add(role)
    db.commit()
    user = User(household_id=household.id, role_id=role.id, display_name="Admin")
    db.add(user)
    db.commit()
    return Actor(user_id=str(user.id), household_id=str(household.id), permissions=frozenset({"audit:read"}))


@pytest.fixture
def rig(migrated_db):
    session_factory = _session_factory()
    recorder = SqlAlchemyAuditRecorder(session_factory)
    return recorder, session_factory, migrated_db


def test_empty_chain_is_trivially_intact(rig):
    _recorder, session_factory, _db = rig
    result = verify_chain_integrity(session_factory)
    assert result.intact is True
    assert result.checked == 0


def test_first_record_chains_from_the_genesis_hash(rig):
    recorder, session_factory, db = rig
    recorder.record(actor=None, action="a", target_type="t", target_id=None, outcome="success")

    row = db.scalars(select(AuditEvent)).first()
    assert row.sequence_number == 1
    assert row.previous_hash == GENESIS_HASH


def test_sequence_numbers_and_previous_hash_chain_across_records(rig):
    recorder, session_factory, db = rig
    recorder.record(actor=None, action="a", target_type="t", target_id=None, outcome="success")
    recorder.record(actor=None, action="b", target_type="t", target_id=None, outcome="success")
    recorder.record(actor=None, action="c", target_type="t", target_id=None, outcome="success")

    rows = list(db.scalars(select(AuditEvent).order_by(AuditEvent.sequence_number)))
    assert [r.sequence_number for r in rows] == [1, 2, 3]
    assert rows[1].previous_hash == rows[0].record_hash
    assert rows[2].previous_hash == rows[1].record_hash


def test_verify_chain_integrity_passes_for_untampered_records(rig):
    recorder, session_factory, _db = rig
    for i in range(5):
        recorder.record(actor=None, action=f"action-{i}", target_type="t", target_id=None, outcome="success")

    result = verify_chain_integrity(session_factory)
    assert result.intact is True
    assert result.checked == 5
    assert result.broken_at_sequence is None


def test_tampering_with_a_historical_record_is_detected(rig):
    """The Definition of Done, literally: modify a historical row
    directly (bypassing SqlAlchemyAuditRecorder entirely, the way an
    attacker with raw database access would) and confirm the integrity
    check flags it."""
    recorder, session_factory, db = rig
    recorder.record(actor=None, action="pin.verified", target_type="user", target_id=None, outcome="success")
    recorder.record(actor=None, action="pin.verified", target_type="user", target_id=None, outcome="success")
    recorder.record(actor=None, action="pin.verified", target_type="user", target_id=None, outcome="success")

    assert verify_chain_integrity(session_factory).intact is True

    tampered = db.scalars(select(AuditEvent).where(AuditEvent.sequence_number == 2)).first()
    db.execute(update(AuditEvent).where(AuditEvent.id == tampered.id).values(outcome="failure"))
    db.commit()

    result = verify_chain_integrity(session_factory)
    assert result.intact is False
    assert result.broken_at_sequence == 2


def test_tampering_with_metadata_is_also_detected(rig):
    """Not just the obviously-sensitive fields - any field covered by the
    hash, including metadata, breaks the chain if altered."""
    recorder, session_factory, db = rig
    recorder.record(
        actor=None, action="pin.verified", target_type="user", target_id=None, outcome="success", metadata={"n": 1}
    )

    row = db.scalars(select(AuditEvent)).first()
    db.execute(update(AuditEvent).where(AuditEvent.id == row.id).values(event_metadata={"n": 999}))
    db.commit()

    result = verify_chain_integrity(session_factory)
    assert result.intact is False
    assert result.broken_at_sequence == 1


def test_tampering_breaks_the_chain_for_every_record_after_it(rig):
    """A tampered record's own hash no longer matches, which is caught
    immediately at that record - but proves the point that everything
    after it is now unverifiable relative to a trusted starting hash too,
    since previous_hash comparisons downstream would no longer line up
    with a legitimately recomputed chain."""
    recorder, session_factory, db = rig
    recorder.record(actor=None, action="a", target_type="t", target_id=None, outcome="success")
    recorder.record(actor=None, action="b", target_type="t", target_id=None, outcome="success")
    recorder.record(actor=None, action="c", target_type="t", target_id=None, outcome="success")

    first = db.scalars(select(AuditEvent).where(AuditEvent.sequence_number == 1)).first()
    db.execute(update(AuditEvent).where(AuditEvent.id == first.id).values(action="tampered"))
    db.commit()

    result = verify_chain_integrity(session_factory)
    assert result.intact is False
    assert result.broken_at_sequence == 1  # caught at the earliest possible point


def test_deleting_a_historical_record_is_detected(rig):
    """Deleting a row breaks the previous_hash chain for the record that
    followed it, since that record's stored previous_hash no longer
    matches any record still present."""
    recorder, session_factory, db = rig
    recorder.record(actor=None, action="a", target_type="t", target_id=None, outcome="success")
    recorder.record(actor=None, action="b", target_type="t", target_id=None, outcome="success")

    first = db.scalars(select(AuditEvent).where(AuditEvent.sequence_number == 1)).first()
    db.delete(first)
    db.commit()

    result = verify_chain_integrity(session_factory)
    assert result.intact is False
    assert result.reason == "previous_hash_mismatch"


# --- AuditLogService: Einsicht in Auditdaten wird selbst auditiert ---------


def test_listing_audit_events_requires_audit_read_permission(rig):
    _recorder, session_factory, _db = rig
    audit = SqlAlchemyAuditRecorder(session_factory)
    service = AuditLogService(session_factory, audit)
    unauthorized = make_actor()

    with pytest.raises(AuthorizationError):
        service.list_events(unauthorized)


def test_listing_audit_events_returns_them_most_recent_first(rig):
    recorder, session_factory, db = rig
    recorder.record(actor=None, action="a", target_type="t", target_id=None, outcome="success")
    recorder.record(actor=None, action="b", target_type="t", target_id=None, outcome="success")

    service = AuditLogService(session_factory, recorder)
    admin = _make_real_admin_actor(db)

    events = service.list_events(admin)
    assert [e.action for e in events[:2]] == ["b", "a"]


def test_viewing_audit_events_is_itself_recorded_as_a_chained_event(rig):
    """DEC-136: "Relevante Einsicht in Auditdaten ebenfalls auditieren"."""
    recorder, session_factory, db = rig
    recorder.record(actor=None, action="a", target_type="t", target_id=None, outcome="success")

    service = AuditLogService(session_factory, recorder)
    admin = _make_real_admin_actor(db)
    service.list_events(admin)

    rows = list(db.scalars(select(AuditEvent).order_by(AuditEvent.sequence_number)))
    assert rows[-1].action == "audit.viewed"
    assert str(rows[-1].actor_user_id) == admin.user_id
    # And the view-event is itself part of the verified chain, not exempt.
    assert verify_chain_integrity(session_factory).intact is True
