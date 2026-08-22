"""S1V2-02-021: `build_home_assistant_adapter()`/
`build_translating_home_assistant_adapter()` close the gap flagged in
`docs/architecture/home-assistant-adapter.md`/`secrets-management.md` -
nothing previously read a stored Home Assistant token back into a working
adapter. Runs against real PostgreSQL, same rig shape as
`test_secret_store.py` (S1V2-02-013), since the behaviour under test is
precisely "what SecretStore currently has stored for this integration"."""

import os

import pytest
from cryptography.fernet import Fernet
from home_assistant_adapter import HomeAssistantAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.audit import InMemoryAuditRecorder
from app.db.models import Household, Integration
from app.secret_store import SecretStore
from app.services.ha_device_adapter import TranslatingHomeAssistantAdapter
from app.services.ha_provisioning import (
    HOME_ASSISTANT_ACCESS_TOKEN_SECRET_KEY,
    build_home_assistant_adapter,
    build_translating_home_assistant_adapter,
)
from tests.db_conftest import migrated_db, requires_database  # noqa: F401
from tests.fakes import make_actor

pytestmark = [requires_database, pytest.mark.security]


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
    store = SecretStore(session_factory=_session_factory(), audit=InMemoryAuditRecorder(), fernet_factory=lambda: Fernet(key))
    admin = make_actor("integrations:manage", household_id=str(household.id))
    return store, admin, str(integration.id)


def test_returns_none_when_no_token_is_configured_yet(rig):
    """Not-yet-onboarded is an ordinary state, not an error - local-first
    (docs/product-manifest.md §2) requires this to never raise."""
    store, _admin, integration_id = rig

    adapter = build_home_assistant_adapter(store, integration_id=integration_id, base_url="http://ha.invalid")

    assert adapter is None


def test_returns_a_working_adapter_once_a_token_is_stored(rig):
    store, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key=HOME_ASSISTANT_ACCESS_TOKEN_SECRET_KEY, value="hass-token-abc123")

    adapter = build_home_assistant_adapter(store, integration_id=integration_id, base_url="http://ha.invalid")

    assert isinstance(adapter, HomeAssistantAdapter)


def test_translating_variant_wraps_the_adapter(rig):
    store, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key=HOME_ASSISTANT_ACCESS_TOKEN_SECRET_KEY, value="hass-token-abc123")

    adapter = build_translating_home_assistant_adapter(store, integration_id=integration_id, base_url="http://ha.invalid")

    assert isinstance(adapter, TranslatingHomeAssistantAdapter)


def test_translating_variant_also_returns_none_when_not_configured(rig):
    store, _admin, integration_id = rig

    adapter = build_translating_home_assistant_adapter(store, integration_id=integration_id, base_url="http://ha.invalid")

    assert adapter is None


def test_uses_the_configured_base_url_and_token(rig):
    """Not just "an adapter comes back" - it must be wired to exactly the
    stored token and the base_url the caller passed in, not some default
    or leftover state from a previous adapter."""
    store, admin, integration_id = rig
    store.set_secret(admin, integration_id=integration_id, key=HOME_ASSISTANT_ACCESS_TOKEN_SECRET_KEY, value="hass-token-xyz789")

    adapter = build_home_assistant_adapter(store, integration_id=integration_id, base_url="http://ha.example.internal:8123")

    assert adapter._client._base_url == "http://ha.example.internal:8123"
    assert adapter._client._access_token == "hass-token-xyz789"
