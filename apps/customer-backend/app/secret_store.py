"""Encrypted, access-restricted secret storage per integration
(S1V2-02-013).

DEC-118: secrets are stored only when technically required - this module
exists specifically because a vendor-integration credential (e.g. a
Home Assistant long-lived access token) cannot function without being
persisted somewhere. Wherever storage is unavoidable it is always
encrypted at rest, never plaintext, and never mixed into
`Integration.config` (general-purpose, non-secret JSON - see that
model's docstring). Storage is scoped per integration, never a
household-wide or global secret bag. `revoke_secret()` deletes the row
outright rather than soft-deleting it: "möglichst nicht speichern"
means nothing lingers once a credential is no longer needed.
"""

import os
import uuid
from collections.abc import Callable

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .audit import AuditRecorder
from .authorization import Actor, CrossHouseholdAccessError, require_permission
from .db.models import Integration, IntegrationSecret

SECRETS_ENCRYPTION_KEY_ENV = "SECRETS_ENCRYPTION_KEY"


class SecretsEncryptionKeyMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            f"{SECRETS_ENCRYPTION_KEY_ENV} is not set - see infrastructure/docker-compose/.env.example. "
            "Generate one with Fernet.generate_key()."
        )


class IntegrationNotFoundError(ValueError):
    def __init__(self, integration_id: str) -> None:
        super().__init__(f"Integration '{integration_id}' does not exist.")
        self.integration_id = integration_id


class SecretNotFoundError(KeyError):
    def __init__(self, integration_id: str, key: str) -> None:
        super().__init__(f"No secret '{key}' stored for integration '{integration_id}'.")
        self.integration_id = integration_id
        self.key = key


def load_fernet_from_env() -> Fernet:
    raw = os.environ.get(SECRETS_ENCRYPTION_KEY_ENV)
    if not raw:
        raise SecretsEncryptionKeyMissingError()
    return Fernet(raw.encode("utf-8"))


class SecretStore:
    """Deliberately its own session_factory, outside the UnitOfWork/
    Repository layer used by ordinary domain services - same rationale as
    AuditRecorder (app/audit.py): a security-sensitive, cross-cutting
    concern gets its own narrow, auditable surface rather than being
    routed through general-purpose repositories."""

    def __init__(
        self,
        session_factory: sessionmaker,
        audit: AuditRecorder,
        fernet_factory: Callable[[], Fernet] = load_fernet_from_env,
    ) -> None:
        self._session_factory = session_factory
        self._audit = audit
        self._fernet_factory = fernet_factory

    def set_secret(self, actor: Actor, *, integration_id: str, key: str, value: str) -> None:
        """Also serves as rotation - overwrites any existing value for
        this (integration, key) outright, the same "reset, not recover"
        shape already established for the household PIN (S1V2-02-011)."""
        require_permission(actor, "integrations:manage")
        fernet = self._fernet_factory()
        ciphertext = fernet.encrypt(value.encode("utf-8")).decode("ascii")

        with self._session_factory() as session:
            integration = session.get(Integration, uuid.UUID(integration_id))
            if integration is None:
                raise IntegrationNotFoundError(integration_id)
            if str(integration.household_id) != actor.household_id:
                self._audit.record(
                    actor=actor,
                    action="secret.blocked",
                    target_type="integration",
                    target_id=integration_id,
                    outcome="failure",
                    metadata={"key": key, "reason": "cross_household"},
                )
                raise CrossHouseholdAccessError()

            existing = session.scalars(
                select(IntegrationSecret).where(
                    IntegrationSecret.integration_id == uuid.UUID(integration_id), IntegrationSecret.key == key
                )
            ).first()
            if existing is not None:
                existing.ciphertext = ciphertext
            else:
                session.add(
                    IntegrationSecret(integration_id=uuid.UUID(integration_id), key=key, ciphertext=ciphertext)
                )
            session.commit()

        self._audit.record(
            actor=actor,
            action="secret.set",
            target_type="integration",
            target_id=integration_id,
            outcome="success",
            metadata={"key": key},
        )

    def revoke_secret(self, actor: Actor, *, integration_id: str, key: str) -> None:
        require_permission(actor, "integrations:manage")
        with self._session_factory() as session:
            integration = session.get(Integration, uuid.UUID(integration_id))
            if integration is not None and str(integration.household_id) != actor.household_id:
                self._audit.record(
                    actor=actor,
                    action="secret.blocked",
                    target_type="integration",
                    target_id=integration_id,
                    outcome="failure",
                    metadata={"key": key, "reason": "cross_household"},
                )
                raise CrossHouseholdAccessError()

            existing = session.scalars(
                select(IntegrationSecret).where(
                    IntegrationSecret.integration_id == uuid.UUID(integration_id), IntegrationSecret.key == key
                )
            ).first()
            if existing is not None:
                session.delete(existing)
                session.commit()

        self._audit.record(
            actor=actor,
            action="secret.revoked",
            target_type="integration",
            target_id=integration_id,
            outcome="success",
            metadata={"key": key},
        )

    def get_secret(self, *, integration_id: str, key: str) -> str:
        """Internal/system retrieval - e.g. a future integration adapter
        connecting to its remote service. No Actor: this is a
        server-to-server call, not a user-initiated action (matching the
        shape of HouseholdPinService.verify_pin), but every access is
        still audited so a leaked-credential investigation has a trail."""
        with self._session_factory() as session:
            existing = session.scalars(
                select(IntegrationSecret).where(
                    IntegrationSecret.integration_id == uuid.UUID(integration_id), IntegrationSecret.key == key
                )
            ).first()
            ciphertext = existing.ciphertext if existing is not None else None

        if ciphertext is None:
            self._audit.record(
                actor=None,
                action="secret.access_failed",
                target_type="integration",
                target_id=integration_id,
                outcome="failure",
                metadata={"key": key, "reason": "not_found"},
            )
            raise SecretNotFoundError(integration_id, key)

        fernet = self._fernet_factory()
        try:
            plaintext = fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken:
            self._audit.record(
                actor=None,
                action="secret.access_failed",
                target_type="integration",
                target_id=integration_id,
                outcome="failure",
                metadata={"key": key, "reason": "invalid_token"},
            )
            raise

        self._audit.record(
            actor=None,
            action="secret.accessed",
            target_type="integration",
            target_id=integration_id,
            outcome="success",
            metadata={"key": key},
        )
        return plaintext

    def has_secret(self, *, integration_id: str, key: str) -> bool:
        """Existence check without decrypting or auditing an access -
        for status/health checks that need to know *whether* credentials
        are configured, not their value."""
        with self._session_factory() as session:
            existing = session.scalars(
                select(IntegrationSecret).where(
                    IntegrationSecret.integration_id == uuid.UUID(integration_id), IntegrationSecret.key == key
                )
            ).first()
        return existing is not None
