"""S1V2-02-013 Definition of Done (diagnostics half): "Tests, dass
Diagnoseexporte Testsecrets nicht enthalten" - proven by setting a real
secret via SecretStore and asserting it is absent, byte-for-byte,
anywhere in the exported diagnostic structure."""

import json
import os

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.audit import InMemoryAuditRecorder
from app.db.models import Household, Integration
from app.diagnostics import export_household_integrations
from app.secret_store import SecretStore
from tests.db_conftest import migrated_db, requires_database  # noqa: F401
from tests.fakes import make_actor

pytestmark = [requires_database, pytest.mark.security]

TEST_SECRET_VALUE = "hass-super-secret-test-token-98765"


def _session_factory():
    engine = create_engine(os.environ["DATABASE_URL"])
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def rig(migrated_db):
    household = Household(name="Test", product_class="pi")
    migrated_db.add(household)
    migrated_db.commit()
    integration = Integration(
        household_id=household.id,
        type="home_assistant",
        status="connected",
        config={"host": "homeassistant.local", "port": 8123},
    )
    migrated_db.add(integration)
    migrated_db.commit()

    session_factory = _session_factory()
    key = Fernet.generate_key()
    store = SecretStore(session_factory=session_factory, audit=InMemoryAuditRecorder(), fernet_factory=lambda: Fernet(key))
    admin = make_actor("integrations:manage", household_id=str(household.id))
    store.set_secret(admin, integration_id=str(integration.id), key="long_lived_token", value=TEST_SECRET_VALUE)

    return session_factory, str(household.id), str(integration.id)


def test_diagnostic_export_does_not_contain_the_secret_value(rig):
    session_factory, household_id, _integration_id = rig
    export = export_household_integrations(session_factory, household_id=household_id)

    serialized = json.dumps(export)
    assert TEST_SECRET_VALUE not in serialized


def test_diagnostic_export_still_contains_non_secret_integration_metadata(rig):
    """Proves the export isn't just empty/stripped-to-nothing - it
    genuinely includes the non-secret fields, only the secret is absent."""
    session_factory, household_id, integration_id = rig
    export = export_household_integrations(session_factory, household_id=household_id)

    assert len(export) == 1
    assert export[0]["id"] == integration_id
    assert export[0]["type"] == "home_assistant"
    assert export[0]["status"] == "connected"
    assert export[0]["config"]["host"] == "homeassistant.local"
    assert export[0]["config"]["port"] == 8123


def test_diagnostic_export_redacts_secret_shaped_config_values(rig, migrated_db):
    """Second, independent safety net: even if a secret ever ended up in
    the general-purpose (documented non-secret) config by operator
    mistake, the existing generic redaction filter still catches it."""
    session_factory, household_id, _integration_id = rig
    stray = Integration(
        household_id=household_id,
        type="mqtt",
        status="connected",
        config={"note": "password=oops-leaked-here"},
    )
    migrated_db.add(stray)
    migrated_db.commit()

    export = export_household_integrations(session_factory, household_id=household_id)
    mqtt_entry = next(e for e in export if e["type"] == "mqtt")
    assert "oops-leaked-here" not in json.dumps(mqtt_entry)
    assert mqtt_entry["config"]["note"] == "password=[REDACTED]"


def test_diagnostic_export_only_includes_the_requested_household(rig, migrated_db):
    session_factory, _household_id, _integration_id = rig
    other_household = Household(name="Other", product_class="mini")
    migrated_db.add(other_household)
    migrated_db.commit()

    export = export_household_integrations(session_factory, household_id=str(other_household.id))
    assert export == []
