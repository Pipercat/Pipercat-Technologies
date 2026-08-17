from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_restart_requires_idempotency_key(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")
    response = client.post("/api/v1/system/restart", json={"expectedVersion": 1})
    assert response.status_code == 422  # missing required header


def test_restart_rejects_version_conflict(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")
    response = client.post(
        "/api/v1/system/restart",
        json={"expectedVersion": 99},
        headers={"Idempotency-Key": "conflict-key"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_restart_is_idempotent_on_retry(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")
    headers = {"Idempotency-Key": "retry-key"}

    first = client.post("/api/v1/system/restart", json={"expectedVersion": 1}, headers=headers)
    assert first.status_code == 200
    first_version = first.json()["data"]["version"]

    # Retry with the same key and a now-stale expectedVersion: must replay
    # the cached first response instead of re-validating or incrementing
    # again (that is the whole point of Idempotency-Key).
    second = client.post("/api/v1/system/restart", json={"expectedVersion": 1}, headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["version"] == first_version
