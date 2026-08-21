"""S1V2-02-027: "Lizenzprüfung funktioniert offline" - the
`GET /api/v1/device/identity` half. Builds a real signed license with a
throwaway keypair and points the app at it via env vars, exactly the way
a real provisioning step would (see scripts/sign_device_license.py) -
no network call anywhere in this file, no mocking of the verification
logic itself (that's already covered end-to-end in test_device_identity.py).
"""

import base64
from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.device_identity import DeviceIdentity, sign_device_identity
from app.main import app
from app.product_class import ProductClass

client = TestClient(app)


def _write_valid_license(tmp_path, monkeypatch, *, private_key=None) -> DeviceIdentity:
    private_key = private_key or Ed25519PrivateKey.generate()
    identity = DeviceIdentity(
        device_id="11111111-1111-1111-1111-111111111111",
        serial_number="SN-0001",
        product_class=ProductClass.PI,
        issued_at=datetime(2026, 8, 21, tzinfo=UTC),
    )
    license = sign_device_identity(identity, private_key)
    license_path = tmp_path / "license.json"
    license_path.write_text(license.model_dump_json())

    monkeypatch.setenv("SYSTEMONE_DEVICE_LICENSE_PATH", str(license_path))
    monkeypatch.setenv(
        "SYSTEMONE_DEVICE_PUBLIC_KEY", base64.b64encode(private_key.public_key().public_bytes_raw()).decode("ascii")
    )
    return identity


def test_returns_the_verified_identity(tmp_path, monkeypatch):
    _write_valid_license(tmp_path, monkeypatch)

    response = client.get("/api/v1/device/identity")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["deviceId"] == "11111111-1111-1111-1111-111111111111"
    assert data["serialNumber"] == "SN-0001"
    assert data["productClass"] == "pi"


def test_missing_configuration_is_a_fail_closed_500(monkeypatch):
    monkeypatch.delenv("SYSTEMONE_DEVICE_LICENSE_PATH", raising=False)
    monkeypatch.delenv("SYSTEMONE_DEVICE_PUBLIC_KEY", raising=False)

    response = client.get("/api/v1/device/identity")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DEVICE_LICENSE_NOT_CONFIGURED"


def test_a_license_signed_by_the_wrong_key_is_a_fail_closed_500(tmp_path, monkeypatch):
    _write_valid_license(tmp_path, monkeypatch)
    # Overwrite the public key with an unrelated one after the license was
    # signed - simulates a tampered/mismatched license file.
    wrong_public_key = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    monkeypatch.setenv("SYSTEMONE_DEVICE_PUBLIC_KEY", base64.b64encode(wrong_public_key).decode("ascii"))

    response = client.get("/api/v1/device/identity")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DEVICE_LICENSE_INVALID"
