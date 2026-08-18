"""S1V2-02-013 Definition of Done (secret-store half): encrypted storage,
per-integration scoping, rotation/revocation, restrictive access rights.
Runs against real PostgreSQL - DEC-118 is precisely about what actually
ends up on disk, which a fake repository cannot prove."""

import os

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.audit import InMemoryAuditRecorder
from app.authorization import AuthorizationError
from app.db.models import Household, Integration, IntegrationSecret
from app.secret_store import (
    IntegrationNotFoundError,
    SecretNotFoundError,
    SecretsEncryptionKeyMissingError,
    SecretStore,
    load_fernet_from_env,
)
from tests.db_conftest import migrated_db, requires_database  # noqa: F401
from tests.fakes import make_actor

pytestmark = requires_database


def _session_factory():
    engine = create_engine(os.environ["DATABASE_URL"])
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def rig(migrated_db):
    household = Household(name="Test", product_class="pi")
    migrated_db.add(household)
    migrated_db.commit()
    integration = Integration(household_id=household.id, type="home_assistant")
    migrated_db.add(integration)
    migrated_db.commit()

    key = Fernet.generate_key()
    audit = InMemoryAuditRecorder()
    store = SecretStore(session_factory=_session_factory(), audit=audit, fernet_factory=lambda: Fernet(key))
    admin = make_actor("integrations:manage")
    return store, migrated_db, audit, admin, str(integration.id)


def test_set_and_get_secret_roundtrips(rig):
    store, _db, _audit, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key="long_lived_token", value="hass-token-abc123")

    assert store.get_secret(integration_id=integration_id, key="long_lived_token") == "hass-token-abc123"


def test_secret_is_never_stored_in_plaintext(rig):
    store, db, _audit, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key="long_lived_token", value="hass-token-abc123")

    row = db.scalars(select(IntegrationSecret).where(IntegrationSecret.integration_id == integration_id)).first()
    assert row.ciphertext != "hass-token-abc123"
    assert "hass-token-abc123" not in row.ciphertext


def test_set_secret_requires_integrations_manage_permission(rig):
    store, _db, _audit, _admin, integration_id = rig
    unauthorized = make_actor()
    with pytest.raises(AuthorizationError):
        store.set_secret(unauthorized, integration_id=integration_id, key="k", value="v")


def test_set_secret_rejects_unknown_integration(rig):
    store, _db, _audit, admin, _integration_id = rig
    with pytest.raises(IntegrationNotFoundError):
        store.set_secret(admin, integration_id="00000000-0000-0000-0000-000000000000", key="k", value="v")


def test_rotate_secret_overwrites_the_previous_value(rig):
    store, _db, _audit, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key="long_lived_token", value="old-value")
    store.set_secret(admin, integration_id=integration_id, key="long_lived_token", value="new-value")

    assert store.get_secret(integration_id=integration_id, key="long_lived_token") == "new-value"


def test_revoke_secret_deletes_it_entirely(rig):
    store, _db, _audit, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key="long_lived_token", value="hass-token-abc123")

    store.revoke_secret(admin, integration_id=integration_id, key="long_lived_token")

    assert store.has_secret(integration_id=integration_id, key="long_lived_token") is False
    with pytest.raises(SecretNotFoundError):
        store.get_secret(integration_id=integration_id, key="long_lived_token")


def test_revoke_secret_requires_integrations_manage_permission(rig):
    store, _db, _audit, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key="k", value="v")
    unauthorized = make_actor()
    with pytest.raises(AuthorizationError):
        store.revoke_secret(unauthorized, integration_id=integration_id, key="k")


def test_get_secret_raises_when_never_set(rig):
    store, _db, _audit, _admin, integration_id = rig
    with pytest.raises(SecretNotFoundError):
        store.get_secret(integration_id=integration_id, key="never_set")


def test_has_secret_reflects_current_state(rig):
    store, _db, _audit, admin, integration_id = rig
    assert store.has_secret(integration_id=integration_id, key="long_lived_token") is False
    store.set_secret(admin, integration_id=integration_id, key="long_lived_token", value="v")
    assert store.has_secret(integration_id=integration_id, key="long_lived_token") is True


def test_secret_operations_are_scoped_per_integration(rig):
    """"Pro Kunde/System getrennt": a secret set for one integration must
    never be visible under another integration's id, even with the same
    key name."""
    store, db, _audit, admin, integration_id = rig
    household = db.scalars(select(Household)).first()
    other = Integration(household_id=household.id, type="other")
    db.add(other)
    db.commit()

    store.set_secret(admin, integration_id=integration_id, key="shared_key_name", value="value-for-first")

    assert store.has_secret(integration_id=str(other.id), key="shared_key_name") is False


def test_audit_trail_records_set_access_and_revoke(rig):
    store, _db, audit, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key="k", value="v")
    store.get_secret(integration_id=integration_id, key="k")
    store.revoke_secret(admin, integration_id=integration_id, key="k")

    actions = [event["action"] for event in audit.events]
    assert actions == ["secret.set", "secret.accessed", "secret.revoked"]


def test_missing_encryption_key_env_var_raises(monkeypatch):
    monkeypatch.delenv("SECRETS_ENCRYPTION_KEY", raising=False)
    with pytest.raises(SecretsEncryptionKeyMissingError):
        load_fernet_from_env()


def test_encryption_key_env_var_is_used_when_present(monkeypatch):
    monkeypatch.setenv("SECRETS_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    fernet = load_fernet_from_env()
    assert fernet.decrypt(fernet.encrypt(b"roundtrip")) == b"roundtrip"
