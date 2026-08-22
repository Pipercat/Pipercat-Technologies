"""API-level proof for S1V2-02-002's Definition of Done: the simulated lamp
is reachable through the same SystemONE API a real device will use later."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_devices_list_includes_the_seeded_simulated_lamp(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")
    response = client.get("/api/v1/devices")
    assert response.status_code == 200
    devices = response.json()["data"]
    assert any(d["name"] == "Wohnzimmerlampe (Simulation)" for d in devices)


def test_send_on_off_command_via_api():
    devices = client.get("/api/v1/devices").json()["data"]
    device_id = devices[0]["id"]

    response = client.post(
        f"/api/v1/devices/{device_id}/commands", json={"type": "on_off", "is_on": True}
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"type": "on_off", "is_on": True}


def test_command_to_unknown_device_returns_device_not_found():
    response = client.post(
        "/api/v1/devices/does-not-exist/commands", json={"type": "on_off", "is_on": True}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEVICE_NOT_FOUND"


def test_invalid_brightness_command_is_rejected_before_reaching_the_domain():
    devices = client.get("/api/v1/devices").json()["data"]
    device_id = devices[0]["id"]

    response = client.post(
        f"/api/v1/devices/{device_id}/commands",
        json={"type": "brightness", "percent": 250},
    )
    assert response.status_code == 422  # FastAPI/Pydantic request validation
