import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def product_class(monkeypatch):
    def _set(value: str):
        monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", value)

    return _set


@pytest.mark.parametrize(
    "cls,nas_allowed,local_ai_allowed",
    [
        ("pi", False, False),
        ("mini", True, False),
        ("server", True, True),
        ("rack", True, True),
    ],
)
def test_feature_gating_matrix(product_class, cls, nas_allowed, local_ai_allowed):
    product_class(cls)

    nas_response = client.get("/api/v1/nas/status")
    assert nas_response.status_code == (200 if nas_allowed else 403)
    if not nas_allowed:
        assert nas_response.json()["error"]["code"] == "FEATURE_NOT_AVAILABLE"

    local_ai_response = client.get("/api/v1/local-ai/status")
    assert local_ai_response.status_code == (200 if local_ai_allowed else 403)
    if not local_ai_allowed:
        assert local_ai_response.json()["error"]["code"] == "FEATURE_NOT_AVAILABLE"


def test_features_list_matches_matrix(product_class):
    product_class("pi")
    response = client.get("/api/v1/features")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["productClass"] == "pi"
    assert "smart_home" in body["data"]["features"]
    assert "nas" not in body["data"]["features"]
    assert "local_ai" not in body["data"]["features"]


def test_unconfigured_product_class_fails_closed(monkeypatch):
    monkeypatch.delenv("SYSTEMONE_PRODUCT_CLASS", raising=False)
    response = client.get("/api/v1/features")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PRODUCT_CLASS_UNKNOWN"


def test_unknown_product_class_value_fails_closed(product_class):
    product_class("toaster")
    response = client.get("/api/v1/features")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PRODUCT_CLASS_UNKNOWN"
