"""S1V2-02-030 Definition of Done: "Clean Setup von Werkszustand bis
nutzbares Dashboard ist ohne manuelle Shell-Eingriffe möglich" - the
timezone/location/rooms half of the first-setup wizard ("Owner, Haus" is
S1V2-02-028's DevicePairingService, already tested in
test_device_pairing.py).
"""

import pytest

from app.authorization import AuthorizationError, CrossHouseholdAccessError
from app.services.setup_wizard import HouseholdNotFoundError, SetupWizardService
from tests.fakes import FakeUnitOfWork, InMemoryAuditRecorder, make_actor


def _rig():
    uow = FakeUnitOfWork()
    household = uow.households.add(name="Musterfamilie", product_class="pi")
    audit = InMemoryAuditRecorder()
    service = SetupWizardService(uow_factory=lambda: uow, audit=audit)
    owner = make_actor("users:manage", "rooms:manage", household_id=household.id)
    return service, uow, audit, owner, household.id


# --- Standort/Zeitzone: minimal erforderliche Genauigkeit --------------------


async def test_set_location_and_timezone_updates_the_household():
    service, uow, _audit, owner, household_id = _rig()

    await service.set_location_and_timezone(
        owner, household_id=household_id, timezone="Europe/Vienna", latitude=48.2082, longitude=16.3738
    )

    household = uow.households.get_by_id(household_id)
    assert household.timezone == "Europe/Vienna"


async def test_location_is_rounded_to_minimal_precision():
    """"Standort nur in minimal erforderlicher Genauigkeit speichern" -
    2 decimal places (~1.1 km), never the raw high-precision input."""
    service, uow, _audit, owner, household_id = _rig()

    await service.set_location_and_timezone(
        owner, household_id=household_id, timezone="Europe/Vienna", latitude=48.208174123, longitude=16.373819456
    )

    household = uow.households.get_by_id(household_id)
    assert household.latitude == 48.21
    assert household.longitude == 16.37


async def test_set_location_without_permission_is_denied():
    service, _uow, _audit, _owner, household_id = _rig()
    unauthorized = make_actor(household_id=household_id)

    with pytest.raises(AuthorizationError):
        await service.set_location_and_timezone(unauthorized, household_id=household_id, timezone="Europe/Vienna")


async def test_set_location_across_households_is_denied():
    service, _uow, _audit, owner, _household_id = _rig()

    with pytest.raises(CrossHouseholdAccessError):
        await service.set_location_and_timezone(owner, household_id="some-other-household", timezone="Europe/Vienna")


async def test_set_location_on_nonexistent_household_raises():
    uow = FakeUnitOfWork()
    audit = InMemoryAuditRecorder()
    service = SetupWizardService(uow_factory=lambda: uow, audit=audit)
    owner = make_actor("users:manage", household_id="never-existed")

    with pytest.raises(HouseholdNotFoundError):
        await service.set_location_and_timezone(owner, household_id="never-existed", timezone="Europe/Vienna")


async def test_location_setting_is_audited():
    service, _uow, audit, owner, household_id = _rig()

    await service.set_location_and_timezone(owner, household_id=household_id, timezone="Europe/Vienna")

    assert audit.events[-1]["action"] == "setup_wizard.location_set"
    assert audit.events[-1]["outcome"] == "success"


# --- Räume --------------------------------------------------------------------


async def test_add_rooms_creates_each_room():
    service, uow, _audit, owner, household_id = _rig()

    created = await service.add_rooms(owner, household_id=household_id, room_names=["Wohnzimmer", "Küche"])

    assert {room.name for room in created} == {"Wohnzimmer", "Küche"}
    assert {room.name for room in uow.rooms.list_by_household(household_id)} == {"Wohnzimmer", "Küche"}


async def test_add_rooms_is_retry_safe_and_never_creates_duplicates():
    """"Teilabbruch wiederaufnehmbar": a retried request with the same
    room names must not double them up."""
    service, uow, _audit, owner, household_id = _rig()

    await service.add_rooms(owner, household_id=household_id, room_names=["Wohnzimmer", "Küche"])
    second_call_created = await service.add_rooms(
        owner, household_id=household_id, room_names=["Wohnzimmer", "Schlafzimmer"]
    )

    assert [room.name for room in second_call_created] == ["Schlafzimmer"]  # "Wohnzimmer" already existed
    assert len(uow.rooms.list_by_household(household_id)) == 3


async def test_add_rooms_duplicate_check_is_case_insensitive():
    service, uow, _audit, owner, household_id = _rig()

    await service.add_rooms(owner, household_id=household_id, room_names=["Wohnzimmer"])
    second_call_created = await service.add_rooms(owner, household_id=household_id, room_names=["WOHNZIMMER"])

    assert second_call_created == []
    assert len(uow.rooms.list_by_household(household_id)) == 1


async def test_add_rooms_without_permission_is_denied():
    service, _uow, _audit, _owner, household_id = _rig()
    unauthorized = make_actor(household_id=household_id)

    with pytest.raises(AuthorizationError):
        await service.add_rooms(unauthorized, household_id=household_id, room_names=["Wohnzimmer"])


# --- Abschluss: nie halb autorisiert -----------------------------------------


async def test_complete_setup_marks_the_household_completed():
    service, uow, _audit, owner, household_id = _rig()

    await service.complete_setup(owner, household_id=household_id)

    assert uow.households.get_by_id(household_id).setup_completed_at is not None


async def test_complete_setup_is_idempotent():
    service, uow, _audit, owner, household_id = _rig()

    await service.complete_setup(owner, household_id=household_id)
    first_completed_at = uow.households.get_by_id(household_id).setup_completed_at

    await service.complete_setup(owner, household_id=household_id)
    second_completed_at = uow.households.get_by_id(household_id).setup_completed_at

    assert first_completed_at == second_completed_at


async def test_complete_setup_without_permission_is_denied():
    service, _uow, _audit, _owner, household_id = _rig()
    unauthorized = make_actor(household_id=household_id)

    with pytest.raises(AuthorizationError):
        await service.complete_setup(unauthorized, household_id=household_id)


# --- Fortschritt: echter Zustand, kein Raten ("wiederaufnehmbar") -----------


async def test_progress_reports_real_current_state_not_a_guess():
    service, _uow, _audit, owner, household_id = _rig()

    initial = await service.get_progress(owner, household_id=household_id)
    assert initial.completed is False
    assert initial.existing_room_names == []

    await service.set_location_and_timezone(owner, household_id=household_id, timezone="Europe/Vienna", latitude=48.2, longitude=16.4)
    await service.add_rooms(owner, household_id=household_id, room_names=["Wohnzimmer"])

    mid = await service.get_progress(owner, household_id=household_id)
    assert mid.timezone == "Europe/Vienna"
    assert mid.existing_room_names == ["Wohnzimmer"]
    assert mid.completed is False

    await service.complete_setup(owner, household_id=household_id)
    final = await service.get_progress(owner, household_id=household_id)
    assert final.completed is True


async def test_progress_for_nonexistent_household_raises():
    uow = FakeUnitOfWork()
    audit = InMemoryAuditRecorder()
    service = SetupWizardService(uow_factory=lambda: uow, audit=audit)
    owner = make_actor("users:manage", household_id="never-existed")

    with pytest.raises(HouseholdNotFoundError):
        await service.get_progress(owner, household_id="never-existed")
