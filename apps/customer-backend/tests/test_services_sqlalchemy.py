"""Integration proof that the real SqlAlchemyUnitOfWork/repositories (not
just the fakes from S1V2-02-003's unit tests) actually work end-to-end
against PostgreSQL, including the transaction boundary."""

import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.audit import InMemoryAuditRecorder
from app.auth import AuthenticationService, hash_password
from app.auth.sessions import SessionStore
from app.db.models import Household, Integration, Role, User
from app.roles import ROLE_PERMISSIONS
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
    actor = make_actor("rooms:manage", "rooms:read", household_id=str(household.id))

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
    actor = make_actor("devices:manage", household_id=str(household.id))

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


async def test_authentication_service_works_against_real_postgres(migrated_db):
    household = Household(name="Test", product_class="pi")
    migrated_db.add(household)
    migrated_db.commit()

    # "member" (with "rooms:read" already among its permissions) is seeded
    # by alembic/versions/0005_seed_role_catalog.py (S1V2-02-028) - look
    # it up rather than creating a duplicate, which would violate
    # roles.key's uniqueness constraint.
    role = migrated_db.scalars(select(Role).where(Role.key == "member")).one()

    user = User(
        household_id=household.id,
        role_id=role.id,
        display_name="Real DB User",
        password_hash=hash_password("hunter2-but-a-real-passphrase"),
    )
    migrated_db.add(user)
    migrated_db.commit()

    service = AuthenticationService(
        uow_factory=_uow_factory, sessions=SessionStore(), audit=InMemoryAuditRecorder()
    )

    token, actor = await service.login(
        user_id=str(user.id), password="hunter2-but-a-real-passphrase", device_label="integration-test"
    )
    # Full real "member" permission set (app.roles.ROLE_PERMISSIONS), not a
    # hand-picked subset - proves login() loads whatever the seeded
    # catalog actually grants, not just one permission that happens to
    # also be in it.
    assert actor.permissions == ROLE_PERMISSIONS["member"]

    resolved_actor = await service.authenticate(token)
    assert resolved_actor.user_id == str(user.id)
