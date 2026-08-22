"""One-time/rotatable device setup secret (S1V2-02-027).

"Setup-Secret einmalig/rotierbar und getrennt von sichtbarer
Seriennummer": a random value independent of `DeviceIdentity.serial_number`
(app/device_identity.py) - never derived from it, so knowing the visible
serial number alone (printed on a label, photographed, read off a QR
code after the fact) never lets anyone compute or guess the setup
secret. Only its SHA-256 hash is ever persisted, mirroring how
`app/db/models.py`'s password/PIN columns are `*_hash` only.

"Kopierter QR-Code allein reicht nicht zur Übernahme eines anderen
Geräts": the QR a customer scans during initial setup is expected to
encode the current, *unconsumed* setup secret alongside the serial
number. `claim()` marks a secret consumed on its first successful use -
irreversibly, until an explicit `rotate()` - so a QR code copied/
photographed *after* the real owner has already claimed the device can
never succeed a second time; the stored hash it would be checked against
already belongs to a spent, one-time value. This does not (and cannot,
in software alone) prevent someone who photographs the QR code *before*
the real owner claims it from winning that race - that is a physical/
logistics-security question (tamper-evident packaging, etc.), not
something this module claims to solve.
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

_SECRET_BYTES = 32


class DeviceSetupSecretService:
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path

    def generate(self) -> str:
        """Also serves as `rotate()` - overwrites any existing state with
        a fresh, unconsumed secret, the same "reset, not recover" shape
        already established for the household PIN (S1V2-02-011)."""
        plaintext = secrets.token_urlsafe(_SECRET_BYTES)
        self._write_state(secret_hash=self._hash(plaintext), consumed=False)
        return plaintext

    def rotate(self) -> str:
        return self.generate()

    def claim(self, candidate_secret: str) -> bool:
        """Returns `True` exactly once per `generate()`/`rotate()` call -
        every subsequent attempt with the same (or any other) secret
        returns `False` until the secret is rotated again."""
        state = self._read_state()
        if state is None or state["consumed"]:
            return False
        if not secrets.compare_digest(state["secret_hash"], self._hash(candidate_secret)):
            return False

        self._write_state(secret_hash=state["secret_hash"], consumed=True)
        return True

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _read_state(self) -> dict | None:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def _write_state(self, *, secret_hash: str, consumed: bool) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps({"secret_hash": secret_hash, "consumed": consumed, "updated_at": datetime.now(UTC).isoformat()}),
            encoding="utf-8",
        )
