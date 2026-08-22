"""S1V2-02-027 Definition of Done: "Lizenzprüfung funktioniert offline"
(the sign/verify round-trip - no network call anywhere in this file) and
the structural half of "kopierter QR-Code allein reicht nicht zur
Übernahme eines anderen Geräts": a license only verifies against the
exact identity + exact key pair it was signed with - copying it onto a
different serial number, product class, or device_id, or verifying it
against a different key, must fail.
"""

from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.device_identity import (
    DeviceIdentity,
    DeviceLicenseInvalidError,
    SignedDeviceLicense,
    sign_device_identity,
    verify_device_license,
)
from app.product_class import ProductClass


def _identity(**overrides) -> DeviceIdentity:
    defaults = {
        "device_id": "11111111-1111-1111-1111-111111111111",
        "serial_number": "SN-0001",
        "product_class": ProductClass.PI,
        "issued_at": datetime(2026, 8, 21, tzinfo=UTC),
    }
    return DeviceIdentity(**{**defaults, **overrides})


def test_a_validly_signed_license_verifies():
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes_raw()
    identity = _identity()

    license = sign_device_identity(identity, private_key)
    verified = verify_device_license(license, public_key_bytes)

    assert verified == identity


def test_verification_fails_against_the_wrong_public_key():
    private_key = Ed25519PrivateKey.generate()
    wrong_public_key_bytes = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    license = sign_device_identity(_identity(), private_key)

    with pytest.raises(DeviceLicenseInvalidError):
        verify_device_license(license, wrong_public_key_bytes)


def test_verification_fails_if_the_serial_number_is_swapped_after_signing():
    """A copied license cannot be re-pointed at a different device by
    editing the visible serial number - the signature covers the whole
    identity, not just an opaque token alongside it."""
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes_raw()
    license = sign_device_identity(_identity(), private_key)

    tampered = SignedDeviceLicense(
        identity=_identity(serial_number="SN-STOLEN"), signature=license.signature
    )

    with pytest.raises(DeviceLicenseInvalidError):
        verify_device_license(tampered, public_key_bytes)


def test_verification_fails_if_the_product_class_is_swapped_after_signing():
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes_raw()
    license = sign_device_identity(_identity(product_class=ProductClass.PI), private_key)

    tampered = SignedDeviceLicense(identity=_identity(product_class=ProductClass.RACK), signature=license.signature)

    with pytest.raises(DeviceLicenseInvalidError):
        verify_device_license(tampered, public_key_bytes)


def test_verification_fails_on_a_corrupted_signature():
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes_raw()
    license = sign_device_identity(_identity(), private_key)

    corrupted = SignedDeviceLicense(identity=license.identity, signature=license.signature[:-4] + "abcd")

    with pytest.raises(DeviceLicenseInvalidError):
        verify_device_license(corrupted, public_key_bytes)
