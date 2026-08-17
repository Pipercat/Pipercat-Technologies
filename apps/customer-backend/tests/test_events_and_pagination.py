from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_recent_events_starts_empty_and_paginates(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")

    response = client.get("/api/v1/events/recent")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["items"] == []
    assert body["data"]["nextCursor"] is None


def test_restart_publishes_an_event_visible_via_recent_events(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")

    restart = client.post(
        "/api/v1/system/restart",
        json={"expectedVersion": 1},
        headers={"Idempotency-Key": "test-events-key-1"},
    )
    assert restart.status_code == 200

    events = client.get("/api/v1/events/recent", params={"limit": 1})
    body = events.json()
    assert body["data"]["items"][0]["type"] == "system.restart_requested"


def test_pagination_cursor_advances(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")

    state_version = 1
    for i in range(3):
        response = client.post(
            "/api/v1/system/restart",
            json={"expectedVersion": state_version},
            headers={"Idempotency-Key": f"cursor-test-{i}"},
        )
        assert response.status_code == 200
        state_version = response.json()["data"]["version"]

    page1 = client.get("/api/v1/events/recent", params={"limit": 2}).json()["data"]
    assert len(page1["items"]) == 2
    assert page1["nextCursor"] is not None

    page2 = client.get(
        "/api/v1/events/recent", params={"limit": 2, "cursor": page1["nextCursor"]}
    ).json()["data"]
    assert page2["items"] != page1["items"]
