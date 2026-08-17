"""Integration proof that the real SqlAlchemyUnitOfWork/repositories (not
just the fakes from S1V2-02-003's unit tests) actually work end-to-end
against PostgreSQL, including the transaction boundary."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.audit import InMemoryAuditRecorder
from app.db.models import Household, Integration
from app.services.device_registration import DeviceRegistrationService
from app.services.rooms import RoomService
from app.uow import SqlAlchemyUnitOfWork
from tests.db_conftest import migrated_db, requires_database  # noqa: F401
from tests.fakes import make_actor

pytestmark = requires_database


def _uow_factory():
    engine = create_engine(os.environ["DATABASE_URL"])
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return SqlAlchemyUnitOfWork(session_factory)


def test_room_service_persists_through_real_postgres(migrated_db):
    household = Household(name="Test", product_class="pi")
    migrated_db.add(household)
    migrated_db.commit()

    service = RoomService(uow_factory=_uow_factory, audit=InMemoryAuditRecorder())
    actor = make_actor("rooms:manage", "rooms:read")

    created = service.create_room(actor, household_id=str(household.id), name="Flur")
    rooms = service.list_rooms(actor, household_id=str(household.id))

    assert [r.name for r in rooms] == ["Flur"]
    assert rooms[0].id == created.id


def test_device_registration_idempotent_through_real_postgres(migrated_db):
    household = Household(name="Test", product_class="pi")
    migrated_db.add(household)
    migrated_db.commit()

    integration = Integration(household_id=household.id, type="home_assistant")
    migrated_db.add(integration)
    migrated_db.commit()

    service = DeviceRegistrationService(uow_factory=_uow_factory, audit=InMemoryAuditRecorder())
    actor = make_actor("devices:manage")

    first = service.register_device(
        actor,
        household_id=str(household.id),
        integration_id=str(integration.id),
        external_id="light.hallway",
        name="Hallway Light",
        device_type="light",
    )
    second = service.register_device(
        actor,
        household_id=str(household.id),
        integration_id=str(integration.id),
        external_id="light.hallway",
        name="Hallway Light (retry)",
        device_type="light",
    )

    assert first.id == second.id
