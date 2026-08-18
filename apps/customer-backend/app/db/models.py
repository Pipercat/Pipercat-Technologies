"""SystemONE core PostgreSQL schema (S1V2-02-001).

Structural schema only — domain/business logic lives in the Service/
Repository layer of S1V2-02-003, not here. Entities match the minimum set
required by the Notion task: Household/System, Room, User, ClientDevice,
Role/Permission, Device, Capability, Integration, Automation,
NotificationPreference, RemoteApproval metadata, plus a separate
append-only AuditEvent table.

Passwords/PINs: only *_hash columns exist — the hashing algorithm itself is
S1V2-02-008's job, this schema just refuses to have a plaintext column.
"""

import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.product_class import ProductClass

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Household(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One SystemONE customer system. Local-first: nothing here references
    SystemONE HQ (see docs/product-manifest.md section 2)."""

    __tablename__ = "households"

    name: Mapped[str] = mapped_column(String(200))
    # Plain str column (not a native Postgres ENUM, to keep future value
    # additions a simple CHECK-constraint migration rather than an
    # ALTER TYPE): validated against app.product_class.ProductClass below.
    # Server-side only, mirrors app/device_identity.py — never
    # client-writable via the API (S1V2-01-003 rule carried into the DB).
    product_class: Mapped[str] = mapped_column(String(20))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Berlin")
    latitude: Mapped[float | None] = mapped_column(default=None)
    longitude: Mapped[float | None] = mapped_column(default=None)

    __table_args__ = (
        CheckConstraint(
            product_class.in_([c.value for c in ProductClass]),  # type: ignore[union-attr]
            name="ck_households_product_class_valid",
        ),
    )


class Room(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "rooms"

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Lookup table — owner/administrator/member/guest/display, matching
    the role set already proven in the existing Node.js pilot
    (mvp/systemone-pi/lib/local-sessions.js) for continuity."""

    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))
    display_name: Mapped[str] = mapped_column(String(200))
    # Never plaintext (S1V2-02-001 rule). Nullable: a guest/display role may
    # be PIN-only. Actual hashing algorithm/verification: S1V2-02-008.
    password_hash: Mapped[str | None] = mapped_column(Text, default=None)
    pin_hash: Mapped[str | None] = mapped_column(Text, default=None)


class ClientDevice(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A paired client (the Flutter app on a phone/tablet) — distinct from
    the smart-home `Device` table below."""

    __tablename__ = "client_devices"

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(200))
    last_seen_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), default=None)


class Integration(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A configured integration, e.g. the mandatory Home Assistant backbone
    (ADR-0002). `config` holds non-secret configuration only — credentials
    belong to the secret/key management system from S1V2-02-013, never
    here."""

    __tablename__ = "integrations"

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    config: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict)


class IntegrationSecret(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encrypted credential material for one integration (S1V2-02-013).
    Deliberately separate from `Integration.config` (DEC-118: encrypted,
    access-restricted secret storage, not mixed into general-purpose JSON
    config). `ciphertext` is never plaintext — see
    `app/secret_store.py::SecretStore` for the only code path that may
    encrypt/decrypt it. No soft-delete: `revoke_secret()` deletes the row
    outright ("möglichst nicht speichern" — nothing is kept once no
    longer needed, not even a decommissioned/tombstoned row)."""

    __tablename__ = "integration_secrets"

    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(100))
    ciphertext: Mapped[str] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("integration_id", "key", name="uq_integration_secrets_integration_key"),)


class Device(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "devices"

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), default=None)
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(300))  # e.g. the Home Assistant entity_id
    name: Mapped[str] = mapped_column(String(200))
    device_type: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("integration_id", "external_id", name="uq_devices_integration_external_id"),
    )


class Capability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Attached metadata on a device (e.g. on_off, brightness). No
    soft-delete — lifecycle follows the owning device."""

    __tablename__ = "capabilities"

    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(100))
    value_type: Mapped[str] = mapped_column(String(30))

    __table_args__ = (UniqueConstraint("device_id", "key", name="uq_capabilities_device_key"),)


class Automation(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "automations"

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    conditions: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    actions: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("user_id", "channel", "category", name="uq_notification_pref_user_channel_category"),
    )


class RemoteApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Metadata only — the actual WireGuard/relay session is out of scope
    here (S1V2-05-015). Short-lived by nature, no soft-delete needed:
    expired/decided rows are historical record, not something a user
    removes."""

    __tablename__ = "remote_approvals"

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    requested_by: Mapped[str] = mapped_column(String(200))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requested_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            status.in_(["pending", "approved", "denied", "expired"]),  # type: ignore[union-attr]
            name="ck_remote_approvals_status_valid",
        ),
    )


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only. Deliberately separate from the mutable fact tables
    above (S1V2-02-001: "Audit-Events getrennt von veränderbaren
    Fachdatensätzen") and has no updated_at/deleted_at — nothing about an
    audit event is ever mutated or removed.

    Manipulation-protection (S1V2-02-014): `sequence_number`/
    `previous_hash`/`record_hash` form a hash chain — each record's hash
    covers its own fields plus the previous record's hash, so editing,
    reordering, or deleting any historical row is detectable via
    `app/audit.py::verify_chain_integrity()`. These three columns are
    only ever set by `SqlAlchemyAuditRecorder.record()`, never computed
    elsewhere, so there is exactly one code path that can produce a
    valid chain."""

    __tablename__ = "audit_events"

    household_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL"), default=None
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), default=None)
    outcome: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    event_metadata: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    sequence_number: Mapped[int] = mapped_column()
    previous_hash: Mapped[str] = mapped_column(String(64))
    record_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(outcome.in_(["success", "failure"]), name="ck_audit_events_outcome_valid"),  # type: ignore[union-attr]
        UniqueConstraint("sequence_number", name="uq_audit_events_sequence_number"),
    )
