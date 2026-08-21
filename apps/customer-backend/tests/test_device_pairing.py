"""S1V2-02-028 Definition of Done: "Replay-, falsches-Gerät- und
bereits-gekoppelt-Tests; QR-Foto allein ermöglicht keinen Zugriff."

Uses `FakeUnitOfWork` (S1V2-02-003) for the household/user creation half
and a real, file-backed `DeviceSetupSecretService` (tmp_path, S1V2-02-027)
for the setup-secret half - no real Postgres or license file needed here,
since neither the fake repositories nor a real filesystem-backed secret
service require one; `get_verified_identity` is injected as a plain
callable so a test can simulate "this is the real device" without a real
signed license file.
"""

from datetime import UTC, datetime

import pytest

from app.device_identity import DeviceIdentity
from app.product_class import ProductClass
from app.services.device_pairing import (
    DevicePairingService,
    InvalidOrConsumedSetupSecretError,
    WrongDeviceError,
)
from app.services.device_setup import DeviceSetupSecretService
from tests.fakes import FakeUnitOfWork, InMemoryAuditRecorder


def _real_identity() -> DeviceIdentity:
    return DeviceIdentity(
        device_id="11111111-1111-1111-1111-111111111111",
        serial_number="SN-REAL-0001",
        product_class=ProductClass.PI,
        issued_at=datetime(2026, 8, 21, tzinfo=UTC),
    )


def _rig(tmp_path):
    uow = FakeUnitOfWork()
    uow.roles.add("owner", "role-owner")
    audit = InMemoryAuditRecorder()
    setup_secret_service = DeviceSetupSecretService(tmp_path / "setup_secret.json")
    service = DevicePairingService(
        uow_factory=lambda: uow,
        audit=audit,
        setup_secret_service=setup_secret_service,
        get_verified_identity=_real_identity,
    )
    return service, uow, audit, setup_secret_service


# --- successful claim ---------------------------------------------------------


async def test_successful_claim_creates_a_household_with_an_owner(tmp_path):
    service, uow, _audit, setup_secret_service = _rig(tmp_path)
    secret = setup_secret_service.generate()

    result = await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=secret,
        household_name="Musterfamilie",
        owner_display_name="Alex",
        owner_password="a-genuinely-long-passphrase",
    )

    household = uow.households.get_by_id(result.household_id)
    owner = uow.users.get_by_id(result.owner_user_id)
    assert household.name == "Musterfamilie"
    assert household.product_class == "pi"
    assert owner.role_id == "role-owner"
    assert owner.display_name == "Alex"


async def test_owner_password_is_stored_only_as_a_hash(tmp_path):
    service, uow, _audit, setup_secret_service = _rig(tmp_path)
    secret = setup_secret_service.generate()

    result = await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=secret,
        household_name="Musterfamilie",
        owner_display_name="Alex",
        owner_password="a-genuinely-long-passphrase",
    )

    owner = uow.users.get_by_id(result.owner_user_id)
    assert owner.password_hash is not None
    assert owner.password_hash != "a-genuinely-long-passphrase"


async def test_successful_claim_is_audited(tmp_path):
    service, _uow, audit, setup_secret_service = _rig(tmp_path)
    secret = setup_secret_service.generate()

    await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=secret,
        household_name="Musterfamilie",
        owner_display_name="Alex",
        owner_password="a-genuinely-long-passphrase",
    )

    assert audit.events[-1]["action"] == "device.paired"
    assert audit.events[-1]["outcome"] == "success"
    assert audit.events[-1]["actor"] is None  # no Actor exists yet at pairing time


# --- falsches Gerät ------------------------------------------------------------


async def test_wrong_serial_number_is_rejected(tmp_path):
    service, _uow, audit, setup_secret_service = _rig(tmp_path)
    secret = setup_secret_service.generate()

    with pytest.raises(WrongDeviceError):
        await service.claim_device(
            serial_number="SN-SOMEONE-ELSES-DEVICE",
            setup_secret=secret,
            household_name="Musterfamilie",
            owner_display_name="Alex",
            owner_password="a-genuinely-long-passphrase",
        )
    assert audit.events[-1]["action"] == "device.pairing_wrong_device"


async def test_wrong_serial_number_does_not_consume_the_setup_secret(tmp_path):
    """A wrong-device attempt must never burn a legitimate secret - the
    real owner can still claim correctly afterward."""
    service, _uow, _audit, setup_secret_service = _rig(tmp_path)
    secret = setup_secret_service.generate()

    with pytest.raises(WrongDeviceError):
        await service.claim_device(
            serial_number="SN-SOMEONE-ELSES-DEVICE",
            setup_secret=secret,
            household_name="Musterfamilie",
            owner_display_name="Alex",
            owner_password="a-genuinely-long-passphrase",
        )

    result = await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=secret,
        household_name="Musterfamilie",
        owner_display_name="Alex",
        owner_password="a-genuinely-long-passphrase",
    )
    assert result.household_id is not None


# --- ungültiges/verbrauchtes Setup-Secret --------------------------------------


async def test_wrong_setup_secret_is_rejected(tmp_path):
    service, _uow, audit, setup_secret_service = _rig(tmp_path)
    setup_secret_service.generate()

    with pytest.raises(InvalidOrConsumedSetupSecretError):
        await service.claim_device(
            serial_number="SN-REAL-0001",
            setup_secret="completely-wrong-guess",
            household_name="Musterfamilie",
            owner_display_name="Alex",
            owner_password="a-genuinely-long-passphrase",
        )
    assert audit.events[-1]["action"] == "device.pairing_rejected"


# --- Replay / bereits gekoppelt / "QR-Foto allein ermöglicht keinen Zugriff" ---


async def test_replaying_the_same_claim_request_a_second_time_fails(tmp_path):
    service, _uow, _audit, setup_secret_service = _rig(tmp_path)
    secret = setup_secret_service.generate()

    await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=secret,
        household_name="Musterfamilie",
        owner_display_name="Alex",
        owner_password="a-genuinely-long-passphrase",
    )

    with pytest.raises(InvalidOrConsumedSetupSecretError):
        await service.claim_device(
            serial_number="SN-REAL-0001",
            setup_secret=secret,
            household_name="A Different Household",
            owner_display_name="Someone Else",
            owner_password="another-passphrase-entirely",
        )


async def test_a_photographed_qr_code_cannot_claim_an_already_paired_device(tmp_path):
    """The exact DoD scenario: whoever has "the QR photo" (serial_number +
    setup_secret) after the device has already been claimed gets nothing -
    not a session, not a household, not any access at all."""
    service, uow, _audit, setup_secret_service = _rig(tmp_path)
    secret = setup_secret_service.generate()
    real_owner_result = await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=secret,
        household_name="Musterfamilie",
        owner_display_name="Alex",
        owner_password="a-genuinely-long-passphrase",
    )
    household_count_after_real_claim = len(uow.households.all())

    with pytest.raises(InvalidOrConsumedSetupSecretError):
        await service.claim_device(
            serial_number="SN-REAL-0001",  # correct serial - only the secret is "stale"
            setup_secret=secret,  # the exact value a photo of the original QR would show
            household_name="Attacker's Household",
            owner_display_name="Attacker",
            owner_password="attacker-password",
        )

    # No new household was created, and the real owner's household is untouched.
    assert len(uow.households.all()) == household_count_after_real_claim
    assert uow.households.get_by_id(real_owner_result.household_id).name == "Musterfamilie"


async def test_rotate_allows_a_deliberate_re_pairing_cycle(tmp_path):
    """The one sanctioned way to re-open pairing after a claim - an
    explicit operator action, never something a stale QR photo alone can
    trigger (see the previous test)."""
    service, _uow, _audit, setup_secret_service = _rig(tmp_path)
    old_secret = setup_secret_service.generate()
    await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=old_secret,
        household_name="First Household",
        owner_display_name="Alex",
        owner_password="a-genuinely-long-passphrase",
    )

    new_secret = setup_secret_service.rotate()

    with pytest.raises(InvalidOrConsumedSetupSecretError):
        await service.claim_device(
            serial_number="SN-REAL-0001",
            setup_secret=old_secret,
            household_name="Should Not Be Created",
            owner_display_name="Nobody",
            owner_password="irrelevant-password",
        )

    result = await service.claim_device(
        serial_number="SN-REAL-0001",
        setup_secret=new_secret,
        household_name="Second Household",
        owner_display_name="Sam",
        owner_password="another-genuinely-long-passphrase",
    )
    assert result.household_id is not None
