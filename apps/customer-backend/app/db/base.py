"""Shared declarative base + mixins for the SystemONE core schema
(S1V2-02-001). See docs/architecture/data-model.md.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    """Stable, non-guessable, non-sequential IDs (S1V2-02-001: "Stabile
    IDs"). UUIDs also avoid leaking row counts/creation order to clients."""

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """Only applied to entities where preserving history/references after
    removal is fachlich nötig (rooms, devices, users, integrations,
    automations, client devices) — not to pure lookup tables (Role,
    Permission, Capability) or append-only/short-lived records (AuditEvent,
    RemoteApproval), per S1V2-02-001's "Soft-delete nur wo fachlich nötig"."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
