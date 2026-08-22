import pytest

from app.authorization import AuthorizationError
from app.services.rooms import RoomService
from tests.fakes import FakeUnitOfWork, InMemoryAuditRecorder, make_actor


@pytest.fixture
def wiring():
    uow = FakeUnitOfWork()
    audit = InMemoryAuditRecorder()
    service = RoomService(uow_factory=lambda: uow, audit=audit)
    return service, uow, audit


def test_create_room_commits_and_records_audit_event(wiring):
    service, uow, audit = wiring
    actor = make_actor("rooms:manage")

    room = service.create_room(actor, household_id="hh-1", name="Wohnzimmer")

    assert room.name == "Wohnzimmer"
    assert uow.committed is True
    assert len(audit.events) == 1
    assert audit.events[0]["action"] == "room.created"
    assert audit.events[0]["target_id"] == room.id
    assert audit.events[0]["outcome"] == "success"


def test_create_room_without_permission_is_denied_and_never_reaches_the_repository(wiring):
    service, uow, audit = wiring
    actor = make_actor()  # no permissions at all

    with pytest.raises(AuthorizationError):
        service.create_room(actor, household_id="hh-1", name="Schlafzimmer")

    assert uow.committed is False
    assert audit.events == []  # denied before any state change - nothing to audit as "done"


def test_list_rooms_requires_read_permission(wiring):
    service, uow, _audit = wiring
    manager = make_actor("rooms:manage")
    service.create_room(manager, household_id="hh-1", name="Küche")

    reader = make_actor("rooms:read")
    rooms = service.list_rooms(reader, household_id="hh-1")
    assert [r.name for r in rooms] == ["Küche"]

    unauthorized = make_actor()
    with pytest.raises(AuthorizationError):
        service.list_rooms(unauthorized, household_id="hh-1")
