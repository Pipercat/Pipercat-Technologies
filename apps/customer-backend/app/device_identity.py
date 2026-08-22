"""Server-side source of truth for this device's product class, plus its
signed device identity/license (S1V2-02-027).

`get_product_class()` deliberately stays exactly as it was
(S1V2-01-003: "Hardwareklasse aus Geräteidentität ableiten, nicht vom
Client frei setzen") - it is already tested (`tests/test_feature_matrix.py`)
against the plain `SYSTEMONE_PRODUCT_CLASS` env var, and every product
class this device could ever run as is a closed, small enum with nothing
sensitive at stake in getting it wrong offline. The signed license below
is a separate, additive capability for identity/serial-number/setup
concerns that genuinely need cryptographic, offline-verifiable proof
(device takeover resistance) - not a replacement for the simpler,
already-correct product-class channel.

Verification (`verify_device_license`/`get_verified_device_identity`) is
the only code path meant to run on a real customer device - it only ever
needs the *public* Ed25519 key. `sign_device_identity` also lives here
(so both directions of the same round-trip are covered by one test
suite), but nothing calls it at runtime: the only caller is
`scripts/sign_device_license.py`, a standalone provisioning-time CLI tool
that is not part of `apps/customer-backend`'s Docker build context (see
that Dockerfile - it `COPY`s only `pyproject.toml` and `app/`, so
`scripts/` at the repo root, and any private key file, structurally
never ends up on a customer image) - "Private Signing Keys nur im
kontrollierten Provisioning/HQ-Kontext, nie auf Kundenimage" holds
because no private key material is ever read, stored, or baked in here;
this module only ever *accepts* one as a caller-supplied argument.
"""

import base64
import json
import os
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel

from .product_class import ProductClass

_ENV_VAR = "SYSTEMONE_PRODUCT_CLASS"
_LICENSE_PATH_ENV_VAR = "SYSTEMONE_DEVICE_LICENSE_PATH"
_PUBLIC_KEY_ENV_VAR = "SYSTEMONE_DEVICE_PUBLIC_KEY"  # base64-encoded raw Ed25519 public key bytes


class ProductClassUnknownError(RuntimeError):
    """Raised when the device's product class cannot be determined. The API
    layer must treat this as fail-closed (deny all feature-gated access),
    never default to the most permissive product class."""


def get_product_class() -> ProductClass:
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        raise ProductClassUnknownError(
            f"{_ENV_VAR} is not set. Product class must be provisioned "
            "server-side; refusing to guess."
        )
    try:
        return ProductClass(raw)
    except ValueError as exc:
        raise ProductClassUnknownError(f"Unknown product class '{raw}'") from exc


# --- signed device identity / license (S1V2-02-027) -------------------------


class DeviceIdentity(BaseModel):
    """Everything a signed license vouches for. `device_id` is a stable,
    non-guessable internal identifier; `serial_number` is the
    human-visible value printed on the device's label/QR code - kept as
    two separate fields since a QR code only needs to carry the latter,
    and a compromised/guessed serial number alone must never be usable as
    an internal identifier anywhere else."""

    device_id: str
    serial_number: str
    product_class: ProductClass
    issued_at: datetime


class SignedDeviceLicense(BaseModel):
    identity: DeviceIdentity
    signature: str  # base64-encoded Ed25519 signature over canonical_identity_bytes(identity)


class DeviceLicenseNotConfiguredError(RuntimeError):
    """No license/public-key has been provisioned at all - distinct from
    `DeviceLicenseInvalidError` (a license exists but fails verification):
    this one is an ordinary "not set up yet" state during development,
    that one is always a hard failure."""


class DeviceLicenseInvalidError(RuntimeError):
    """The license file is malformed, or its signature does not verify
    against the configured public key - fail closed, exactly like
    `ProductClassUnknownError`. Never treat an invalid license as "no
    license" and fall back to a permissive default."""


def canonical_identity_bytes(identity: DeviceIdentity) -> bytes:
    """Deterministic byte representation to sign/verify over - sorted
    keys and fixed separators so the same `DeviceIdentity` always
    produces the same bytes regardless of dict ordering."""
    return json.dumps(identity.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_device_identity(identity: DeviceIdentity, private_key: Ed25519PrivateKey) -> SignedDeviceLicense:
    """Provisioning-time only (see this module's docstring) - never
    called by the running customer-backend service itself."""
    signature = private_key.sign(canonical_identity_bytes(identity))
    return SignedDeviceLicense(identity=identity, signature=base64.b64encode(signature).decode("ascii"))


def verify_device_license(license: SignedDeviceLicense, public_key_bytes: bytes) -> DeviceIdentity:
    """Offline signature verification - no network call, no HQ
    dependency (docs/product-manifest.md §2). Only ever needs the
    *public* key, which is safe to ship on every customer image."""
    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(base64.b64decode(license.signature), canonical_identity_bytes(license.identity))
    except (InvalidSignature, ValueError) as exc:
        raise DeviceLicenseInvalidError("Device license signature verification failed") from exc
    return license.identity


def get_verified_device_identity() -> DeviceIdentity:
    """Reads the license file + public key from provisioning-time
    configuration (mirrors `get_product_class()`'s env-var pattern) and
    verifies it offline. Fail-closed: a missing configuration raises
    `DeviceLicenseNotConfiguredError`, a present-but-broken one raises
    `DeviceLicenseInvalidError` - callers must never treat either as "use
    a default identity"."""
    license_path = os.environ.get(_LICENSE_PATH_ENV_VAR)
    public_key_b64 = os.environ.get(_PUBLIC_KEY_ENV_VAR)
    if not license_path or not public_key_b64:
        raise DeviceLicenseNotConfiguredError(
            f"{_LICENSE_PATH_ENV_VAR}/{_PUBLIC_KEY_ENV_VAR} are not both set. "
            "Device license must be provisioned server-side; refusing to guess."
        )

    try:
        raw_license = Path(license_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise DeviceLicenseInvalidError(f"Could not read device license file at {license_path}") from exc

    try:
        license = SignedDeviceLicense.model_validate_json(raw_license)
        public_key_bytes = base64.b64decode(public_key_b64)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DeviceLicenseInvalidError("Malformed device license file or public key") from exc

    return verify_device_license(license, public_key_bytes)
