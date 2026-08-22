"""S1V2-02-026: "UI/API zeigen Status nachvollziehbar" - the read-only
`GET /api/v1/device-compatibility` half. No permission required (public
product information, not household data) - see test_device_compatibility.py
for the registry/model-level tests this endpoint is a thin wrapper around.
"""

import pytest
from fastapi.testclient import TestClient

from app.device_compatibility import (
    DEVICE_COMPATIBILITY_REGISTRY,
    CompatibilityStatus,
    CompatibilityTestEvidence,
    DeviceCompatibilityProfile,
    register_profile,
)
from app.main import app

client = TestClient(app)


@pytest.fixture
def registered_profile():
    profile = DeviceCompatibilityProfile(
        manufacturer="Sonoff",
        model="ZBDongle-P",
        integration_type="zigbee",
        capabilities=["on_off"],
        status=CompatibilityStatus.CERTIFIED,
        test_evidence=CompatibilityTestEvidence(tested_by="qa-team", tested_at="2026-08-21", test_matrix={"pairing": True}),
    )
    register_profile(profile)
    yield profile
    DEVICE_COMPATIBILITY_REGISTRY.clear()


def test_returns_404_for_an_unregistered_device():
    response = client.get(
        "/api/v1/device-compatibility", params={"manufacturer": "Nonexistent", "model": "X", "integrationType": "zigbee"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEVICE_COMPATIBILITY_NOT_FOUND"


def test_returns_the_registered_profile(registered_profile):
    response = client.get(
        "/api/v1/device-compatibility",
        params={"manufacturer": "Sonoff", "model": "ZBDongle-P", "integrationType": "zigbee"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "certified"
    assert data["capabilities"] == ["on_off"]
    assert data["disclaimer"] is None


def test_lookup_is_case_insensitive(registered_profile):
    response = client.get(
        "/api/v1/device-compatibility",
        params={"manufacturer": "SONOFF", "model": "zbdongle-p", "integrationType": "ZIGBEE"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "certified"


def test_beta_profile_includes_its_disclaimer():
    profile = DeviceCompatibilityProfile(manufacturer="Acme", model="Widget", integration_type="generic_ha", status=CompatibilityStatus.BETA)
    register_profile(profile)
    try:
        response = client.get(
            "/api/v1/device-compatibility",
            params={"manufacturer": "Acme", "model": "Widget", "integrationType": "generic_ha"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["disclaimer"] is not None
    finally:
        DEVICE_COMPATIBILITY_REGISTRY.clear()
