"""Secure QR first-pairing process (S1V2-02-028).

"QR enthält keine langlebigen Admin-Credentials": the QR a customer scans
carries only `serial_number` + the current, one-time `setup_secret`
(app/services/device_setup.py, S1V2-02-027) - never a password or session
token. The admin password is chosen fresh by whoever pairs the device,
typed into the app at pairing time, never encoded anywhere.

"Kopplung bindet App/Benutzer an echte Geräteidentität": `claim_device()`
compares the caller-supplied `serial_number` against
`get_verified_device_identity()`'s offline-verified, signed identity
(app/device_identity.py, S1V2-02-027) *before* touching the setup secret
at all - a wrong-device claim attempt never burns a legitimate secret.

"Erster Owner wird atomar gesetzt": enforced by `DeviceSetupSecretService.
claim()`'s own single-consumption guarantee, not by any database-level
locking (there is no household row yet for a lock to target). Within one
process, a synchronous, non-yielding `claim()` call can never interleave
with another coroutine's call to it - only one concurrent pairing attempt
can ever observe an unconsumed secret and win. This assumes the
customer-backend process this runs in is single-process (true for the
local-first Pi/Mini/Server/Rack deployment model, docs/product-manifest.md
§2); a future multi-process deployment would need real file locking in
`DeviceSetupSecretService` for the same guarantee to hold across
processes - see docs/architecture/device-pairing.md's "Bekannte Grenzen".

"Replay ... verhindern": the exact same guarantee - a replayed claim
request presents the same (already-consumed) setup secret, which
`claim()` rejects unconditionally.

Household/User creation happens *after* the secret is successfully
consumed, not before: if the DB transaction below were to fail after an
already-consumed secret, the device would need a manual
`DeviceSetupSecretService.rotate()` to retry - a rare, honestly
documented edge case, safer than the alternative of consuming the secret
only after DB success (which would reopen exactly the TOCTOU race the
secret exists to prevent).
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.audit import AuditRecorder
from app.auth.password_hashing import hash_password
from app.device_identity import DeviceIdentity
from app.services.device_setup import DeviceSetupSecretService
from app.uow import UnitOfWork


class WrongDeviceError(ValueError):
    """The caller-supplied serial number does not match this device's own
    verified identity - never even attempts to consume the setup secret."""


class InvalidOrConsumedSetupSecretError(ValueError):
    """The setup secret is wrong, or has already been consumed by an
    earlier successful pairing (replay, or "already paired") - covers
    both DoD cases with the same underlying guarantee."""


@dataclass(frozen=True)
class PairingResult:
    household_id: str
    owner_user_id: str


class DevicePairingService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        audit: AuditRecorder,
        setup_secret_service: DeviceSetupSecretService,
        get_verified_identity: Callable[[], DeviceIdentity],
    ) -> None:
        self._uow_factory = uow_factory
        self._audit = audit
        self._setup_secret_service = setup_secret_service
        self._get_verified_identity = get_verified_identity

    async def claim_device(
        self,
        *,
        serial_number: str,
        setup_secret: str,
        household_name: str,
        owner_display_name: str,
        owner_password: str,
    ) -> PairingResult:
        # No Actor exists yet - this is the one operation in the whole
        # system that runs before any User/Actor does. Every audit record
        # below passes actor=None, the same precedent already established
        # by app/auth/service.py for pre-authentication system events.
        identity = self._get_verified_identity()

        if identity.serial_number != serial_number:
            self._audit.record(
                actor=None,
                action="device.pairing_wrong_device",
                target_type="device",
                target_id=identity.device_id,
                outcome="failure",
                metadata={"claimedSerialNumber": serial_number},
            )
            raise WrongDeviceError(
                f"Serial number '{serial_number}' does not match this device's own identity."
            )

        if not self._setup_secret_service.claim(setup_secret):
            self._audit.record(
                actor=None,
                action="device.pairing_rejected",
                target_type="device",
                target_id=identity.device_id,
                outcome="failure",
                metadata={"reason": "invalid_or_consumed_setup_secret"},
            )
            raise InvalidOrConsumedSetupSecretError("Setup secret is invalid or has already been used.")

        password_hash = hash_password(owner_password)
        with self._uow_factory() as uow:
            household = uow.households.add(name=household_name, product_class=identity.product_class.value)
            owner_role_id = uow.roles.get_id_by_key("owner")
            assert owner_role_id is not None, '"owner" role must be seeded (see alembic/versions/0005_seed_role_catalog.py)'
            owner = uow.users.add(
                household_id=household.id,
                role_id=owner_role_id,
                display_name=owner_display_name,
                password_hash=password_hash,
            )
            uow.commit()

        self._audit.record(
            actor=None,
            action="device.paired",
            target_type="household",
            target_id=household.id,
            outcome="success",
            metadata={"ownerUserId": owner.id},
        )
        return PairingResult(household_id=household.id, owner_user_id=owner.id)
