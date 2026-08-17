import pytest

from app.authorization import AuthorizationError
from app.services.device_registration import DeviceRegistrationService
from tests.fakes import FakeUnitOfWork, InMemoryAuditRecorder, make_actor


@pytest.fixture
def wiring():
    uow = FakeUnitOfWork()
    audit = InMemoryAuditRecorder()
    service = DeviceRegistrationService(uow_factory=lambda: uow, audit=audit)
    return service, uow, audit


def test_register_device_creates_a_new_record(wiring):
    service, uow, audit = wiring
    actor = make_actor("devices:manage")

    device = service.register_device(
        actor,
        household_id="hh-1",
        integration_id="int-1",
        external_id="light.kitchen",
        name="Kitchen Light",
        device_type="light",
    )

    assert device.external_id == "light.kitchen"
    assert uow.committed is True
    assert audit.events[-1]["action"] == "device.registered"


def test_registering_the_same_external_device_twice_is_idempotent(wiring):
    """S1V2-02-003: 'idempotente Operationen für Provisioning' - a retried
    registration must not create a duplicate device or error."""
    service, uow, audit = wiring
    actor = make_actor("devices:manage")

    first = service.register_device(
        actor,
        household_id="hh-1",
        integration_id="int-1",
        external_id="light.kitchen",
        name="Kitchen Light",
        device_type="light",
    )
    second = service.register_device(
        actor,
        household_id="hh-1",
        integration_id="int-1",
        external_id="light.kitchen",
        name="Kitchen Light (retry)",
        device_type="light",
    )

    assert first.id == second.id
    assert len(uow.devices.list_by_household("hh-1")) == 1
    assert audit.events[-1]["action"] == "device.registration_replayed"
    assert audit.events[-1]["metadata"]["idempotent"] is True


def test_register_device_without_permission_is_denied(wiring):
    service, _uow, audit = wiring
    actor = make_actor()

    with pytest.raises(AuthorizationError):
        service.register_device(
            actor,
            household_id="hh-1",
            integration_id="int-1",
            external_id="light.kitchen",
            name="Kitchen Light",
            device_type="light",
        )

    assert audit.events == []
