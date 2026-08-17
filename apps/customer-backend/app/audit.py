"""Audit hook for security-relevant use cases (S1V2-02-003).

Deliberately its own transaction/session, separate from the UnitOfWork of
the action being audited: a failed audit write must never roll back an
otherwise-successful state change, and a failed state change must still be
auditable as a failure. Manipulation-protection (hash-chaining) is
S1V2-02-014's job; this only defines the recording contract.
"""

import uuid
from typing import Any, Protocol

from sqlalchemy.orm import sessionmaker

from .authorization import Actor
from .db.models import AuditEvent


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
        with self._session_factory() as session:
            session.add(
                AuditEvent(
                    actor_user_id=uuid.UUID(actor.user_id) if actor else None,
                    action=action,
                    target_type=target_type,
                    target_id=uuid.UUID(target_id) if target_id else None,
                    outcome=outcome,
                    event_metadata=metadata or {},
                )
            )
            session.commit()


class InMemoryAuditRecorder:
    """Test/fake implementation - see tests/fakes.py usage."""

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
