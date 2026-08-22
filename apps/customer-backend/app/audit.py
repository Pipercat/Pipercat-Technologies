"""Audit hook for security-relevant use cases (S1V2-02-003), hardened into
a tamper-evident hash-chained log (S1V2-02-014).

Deliberately its own transaction/session, separate from the UnitOfWork of
the action being audited: a failed audit write must never roll back an
otherwise-successful state change, and a failed state change must still be
auditable as a failure.

DEC-138: every record is chained to the one before it (`previousHash`
included in the hash of the current record, whose own hash becomes the
next record's `previousHash`) - a classic hash-chain / tamper-evident
log. Changing, reordering, or deleting any historical row breaks the
chain from that point forward, which `verify_chain_integrity()` detects.
This does not *prevent* a privileged attacker with raw database access
from editing a row - no application-layer mechanism can - but it makes
any such edit detectable, which is what "manipulationsgeschützt" means
here (see docs/architecture/audit-log.md).
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .authorization import Actor, require_permission
from .db.models import AuditEvent

# Named genesis marker (not all-zeros) so a chain's first record is
# unambiguously distinguishable from "previousHash accidentally left
# empty" during review.
GENESIS_HASH = hashlib.sha256(b"SystemONE-Audit-Genesis").hexdigest()


class AuditRecorder(Protocol):
    def record(
        self,
        *,
        actor: Actor | None,
        action: str,
        target_type: str,
        target_id: str | None,
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class AuditEventRecord:
    id: str
    household_id: str | None
    actor_user_id: str | None
    action: str
    target_type: str
    target_id: str | None
    outcome: str
    occurred_at: datetime
    sequence_number: int
    previous_hash: str
    record_hash: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ChainVerificationResult:
    intact: bool
    checked: int
    broken_at_sequence: int | None = None
    reason: str | None = None


def _canonical_payload(
    *,
    household_id: str | None,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str | None,
    outcome: str,
    occurred_at: datetime,
    metadata: dict[str, Any],
    sequence_number: int,
    previous_hash: str,
) -> bytes:
    """Deterministic serialization of everything that must be covered by
    the hash - sorted keys and a fixed separator so the same logical
    record always hashes identically regardless of dict insertion order."""
    payload = {
        "sequenceNumber": sequence_number,
        "previousHash": previous_hash,
        "householdId": household_id,
        "actorUserId": actor_user_id,
        "action": action,
        "targetType": target_type,
        "targetId": target_id,
        "outcome": outcome,
        # Always normalized to UTC before formatting: a timestamptz round
        # -tripped through PostgreSQL comes back with whatever offset the
        # session's TimeZone setting uses, not necessarily "+00:00" - the
        # same instant would otherwise hash differently at write time
        # (always UTC, from datetime.now(UTC)) vs. verify time (as read
        # back), which is not real tampering.
        "occurredAt": occurred_at.astimezone(UTC).isoformat(),
        "metadata": metadata,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_record(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class SqlAlchemyAuditRecorder:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        actor: Actor | None,
        action: str,
        target_type: str,
        target_id: str | None,
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        household_id = None  # no household scoping at the audit-write call site today
        actor_user_id = actor.user_id if actor else None
        occurred_at = datetime.now(UTC)
        event_metadata = metadata or {}

        with self._session_factory() as session:
            # Row-locks the tail of the chain so two concurrent writers
            # can never both compute the same sequence_number/
            # previous_hash - the loser blocks until the winner commits,
            # rather than racing to an inconsistent chain.
            last = session.scalars(
                select(AuditEvent).order_by(AuditEvent.sequence_number.desc()).limit(1).with_for_update()
            ).first()
            sequence_number = (last.sequence_number + 1) if last else 1
            previous_hash = last.record_hash if last else GENESIS_HASH

            payload = _canonical_payload(
                household_id=household_id,
                actor_user_id=actor_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                outcome=outcome,
                occurred_at=occurred_at,
                metadata=event_metadata,
                sequence_number=sequence_number,
                previous_hash=previous_hash,
            )
            record_hash = _hash_record(payload)

            session.add(
                AuditEvent(
                    actor_user_id=uuid.UUID(actor_user_id) if actor_user_id else None,
                    action=action,
                    target_type=target_type,
                    target_id=uuid.UUID(target_id) if target_id else None,
                    outcome=outcome,
                    occurred_at=occurred_at,
                    event_metadata=event_metadata,
                    sequence_number=sequence_number,
                    previous_hash=previous_hash,
                    record_hash=record_hash,
                )
            )
            session.commit()


class InMemoryAuditRecorder:
    """Test/fake implementation - see tests/fakes.py usage. Deliberately
    not hash-chained: the tamper-evidence guarantee is specifically about
    what ends up durably on disk (SqlAlchemyAuditRecorder); a process-
    local list has nothing for an attacker to tamper with between
    process restarts."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(
        self,
        *,
        actor: Actor | None,
        action: str,
        target_type: str,
        target_id: str | None,
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            {
                "actor": actor,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "outcome": outcome,
                "metadata": metadata or {},
            }
        )


def verify_chain_integrity(session_factory: sessionmaker) -> ChainVerificationResult:
    """Recomputes every record's hash from its stored fields and confirms
    it both matches the stored `record_hash` and correctly chains from
    the previous record. Any historical UPDATE - by an attacker, a rogue
    admin, or plain data corruption - changes that record's recomputed
    hash, which no longer matches what was stored, and breaks the chain
    for every record after it. This is the DoD's tamper-test check."""
    with session_factory() as session:
        rows = list(session.scalars(select(AuditEvent).order_by(AuditEvent.sequence_number)))

    expected_previous = GENESIS_HASH
    for checked, row in enumerate(rows, start=1):
        if row.previous_hash != expected_previous:
            return ChainVerificationResult(
                intact=False, checked=checked, broken_at_sequence=row.sequence_number, reason="previous_hash_mismatch"
            )

        payload = _canonical_payload(
            household_id=str(row.household_id) if row.household_id else None,
            actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
            action=row.action,
            target_type=row.target_type,
            target_id=str(row.target_id) if row.target_id else None,
            outcome=row.outcome,
            occurred_at=row.occurred_at,
            metadata=row.event_metadata,
            sequence_number=row.sequence_number,
            previous_hash=row.previous_hash,
        )
        expected_hash = _hash_record(payload)
        if expected_hash != row.record_hash:
            return ChainVerificationResult(
                intact=False, checked=checked, broken_at_sequence=row.sequence_number, reason="record_hash_mismatch"
            )
        expected_previous = row.record_hash

    return ChainVerificationResult(intact=True, checked=len(rows))


class AuditLogService:
    """Read access to the audit log itself - deliberately separate from
    SqlAlchemyAuditRecorder (which only ever appends). DEC-136:
    "Relevante Einsicht in Auditdaten ebenfalls auditieren" - every call
    to list_events() therefore always records one more chained event
    about itself, via the injected AuditRecorder."""

    def __init__(self, session_factory: sessionmaker, audit: AuditRecorder) -> None:
        self._session_factory = session_factory
        self._audit = audit

    def list_events(self, actor: Actor, *, limit: int = 100) -> list[AuditEventRecord]:
        require_permission(actor, "audit:read")

        with self._session_factory() as session:
            stmt = select(AuditEvent).order_by(AuditEvent.sequence_number.desc()).limit(limit)
            rows = list(session.scalars(stmt))

        records = [_to_record(row) for row in rows]
        self._audit.record(
            actor=actor,
            action="audit.viewed",
            target_type="audit_log",
            target_id=None,
            outcome="success",
            metadata={"limit": limit, "returned": len(records)},
        )
        return records


def _to_record(row: AuditEvent) -> AuditEventRecord:
    return AuditEventRecord(
        id=str(row.id),
        household_id=str(row.household_id) if row.household_id else None,
        actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
        action=row.action,
        target_type=row.target_type,
        target_id=str(row.target_id) if row.target_id else None,
        outcome=row.outcome,
        occurred_at=row.occurred_at,
        sequence_number=row.sequence_number,
        previous_hash=row.previous_hash,
        record_hash=row.record_hash,
        metadata=row.event_metadata,
    )
