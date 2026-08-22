"""S1V2-02-027 Definition of Done: "Setup-Secret einmalig/rotierbar und
getrennt von sichtbarer Seriennummer" + the runtime half of "kopierter
QR-Code allein reicht nicht zur Übernahme eines anderen Geräts": once a
setup secret has been successfully claimed, the exact same value must
never succeed again, even if someone else obtains a copy of it later.
"""

from app.services.device_setup import DeviceSetupSecretService


def test_generate_returns_a_secret_independent_of_any_serial_number(tmp_path):
    service = DeviceSetupSecretService(tmp_path / "setup_secret.json")

    secret = service.generate()

    assert len(secret) > 20  # high-entropy, not something guessable/short


def test_claiming_the_freshly_generated_secret_succeeds(tmp_path):
    service = DeviceSetupSecretService(tmp_path / "setup_secret.json")
    secret = service.generate()

    assert service.claim(secret) is True


def test_claiming_the_same_secret_a_second_time_fails(tmp_path):
    """The core "copied QR code doesn't grant a second takeover"
    guarantee: a secret is single-use, irrespective of who presents it."""
    service = DeviceSetupSecretService(tmp_path / "setup_secret.json")
    secret = service.generate()

    assert service.claim(secret) is True
    assert service.claim(secret) is False  # already consumed


def test_claiming_with_a_wrong_secret_fails(tmp_path):
    service = DeviceSetupSecretService(tmp_path / "setup_secret.json")
    service.generate()

    assert service.claim("completely-wrong-guess") is False


def test_claiming_before_any_secret_was_ever_generated_fails(tmp_path):
    service = DeviceSetupSecretService(tmp_path / "setup_secret.json")

    assert service.claim("anything") is False


def test_rotate_invalidates_the_previous_unclaimed_secret(tmp_path):
    service = DeviceSetupSecretService(tmp_path / "setup_secret.json")
    old_secret = service.generate()

    new_secret = service.rotate()

    assert service.claim(old_secret) is False
    assert service.claim(new_secret) is True


def test_rotate_after_a_claim_allows_a_fresh_claim_cycle(tmp_path):
    service = DeviceSetupSecretService(tmp_path / "setup_secret.json")
    first_secret = service.generate()
    service.claim(first_secret)

    second_secret = service.rotate()

    assert service.claim(first_secret) is False  # old, already-spent value stays dead
    assert service.claim(second_secret) is True


def test_two_independent_services_do_not_share_state(tmp_path):
    """Sanity check that state is genuinely scoped to `state_path`, not
    some accidental process-global."""
    service_a = DeviceSetupSecretService(tmp_path / "a.json")
    service_b = DeviceSetupSecretService(tmp_path / "b.json")
    secret_a = service_a.generate()

    assert service_b.claim(secret_a) is False
