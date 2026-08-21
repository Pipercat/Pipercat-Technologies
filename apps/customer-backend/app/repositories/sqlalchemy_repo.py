"""Real, PostgreSQL-backed repository implementations (S1V2-02-003).
Satisfy app.repositories.protocols structurally - no inheritance needed."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Device, Household, Permission, Role, RolePermission, Room, User

from .records import DeviceRecord, HouseholdRecord, RoomRecord, UserRecord


class SqlAlchemyHouseholdRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, name: str, product_class: str) -> HouseholdRecord:
        household = Household(name=name, product_class=product_class)
        self._session.add(household)
        self._session.flush()  # assigns household.id without committing the transaction
        return _to_household_record(household)

    def get_by_id(self, household_id: str) -> HouseholdRecord | None:
        # Household has no SoftDeleteMixin (app/db/models.py) - unlike
        # Room/User/Device, a household is never soft-deleted.
        household = self._session.get(Household, uuid.UUID(household_id))
        return _to_household_record(household) if household is not None else None


class SqlAlchemyRoomRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, *, household_id: str, name: str, integration_id: str | None = None, external_id: str | None = None
    ) -> RoomRecord:
        room = Room(
            household_id=uuid.UUID(household_id),
            name=name,
            integration_id=uuid.UUID(integration_id) if integration_id else None,
            external_id=external_id,
        )
        self._session.add(room)
        self._session.flush()  # assigns room.id without committing the transaction
        return _to_room_record(room)

    def get_by_external_id(self, integration_id: str, external_id: str) -> RoomRecord | None:
        stmt = select(Room).where(
            Room.integration_id == uuid.UUID(integration_id), Room.external_id == external_id, Room.deleted_at.is_(None)
        )
        room = self._session.scalars(stmt).first()
        return _to_room_record(room) if room else None

    def update_name(self, room_id: str, name: str) -> None:
        room = self._session.get(Room, uuid.UUID(room_id))
        if room is not None:
            room.name = name
            self._session.flush()

    def list_by_household(self, household_id: str) -> list[RoomRecord]:
        stmt = select(Room).where(Room.household_id == uuid.UUID(household_id), Room.deleted_at.is_(None))
        return [_to_room_record(r) for r in self._session.scalars(stmt)]


class SqlAlchemyDeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        household_id: str,
        integration_id: str,
        external_id: str,
        name: str,
        device_type: str,
        room_id: str | None = None,
    ) -> DeviceRecord:
        device = Device(
            household_id=uuid.UUID(household_id),
            integration_id=uuid.UUID(integration_id),
            external_id=external_id,
            name=name,
            device_type=device_type,
            room_id=uuid.UUID(room_id) if room_id else None,
        )
        self._session.add(device)
        self._session.flush()
        return _to_device_record(device)

    def get_by_external_id(self, integration_id: str, external_id: str) -> DeviceRecord | None:
        stmt = select(Device).where(
            Device.integration_id == uuid.UUID(integration_id),
            Device.external_id == external_id,
            Device.deleted_at.is_(None),
        )
        device = self._session.scalars(stmt).first()
        return _to_device_record(device) if device else None

    def update(self, device_id: str, *, name: str, room_id: str | None) -> None:
        device = self._session.get(Device, uuid.UUID(device_id))
        if device is not None:
            device.name = name
            device.room_id = uuid.UUID(room_id) if room_id else None
            self._session.flush()

    def list_by_household(self, household_id: str) -> list[DeviceRecord]:
        stmt = select(Device).where(Device.household_id == uuid.UUID(household_id), Device.deleted_at.is_(None))
        return [_to_device_record(d) for d in self._session.scalars(stmt)]


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        household_id: str,
        role_id: str,
        display_name: str,
        password_hash: str | None = None,
        pin_hash: str | None = None,
    ) -> UserRecord:
        user = User(
            household_id=uuid.UUID(household_id),
            role_id=uuid.UUID(role_id),
            display_name=display_name,
            password_hash=password_hash,
            pin_hash=pin_hash,
        )
        self._session.add(user)
        self._session.flush()
        return _to_user_record(user)

    def get_by_id(self, user_id: str) -> UserRecord | None:
        user = self._session.get(User, uuid.UUID(user_id))
        if user is None or user.deleted_at is not None:
            return None
        return _to_user_record(user)

    def get_permissions_for_role(self, role_id: str) -> frozenset[str]:
        stmt = (
            select(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.id == uuid.UUID(role_id))
        )
        return frozenset(self._session.scalars(stmt))

    def set_role(self, user_id: str, role_id: str) -> None:
        user = self._session.get(User, uuid.UUID(user_id))
        if user is not None:
            user.role_id = uuid.UUID(role_id)
            self._session.flush()

    def set_pin_hash(self, user_id: str, pin_hash: str | None) -> None:
        user = self._session.get(User, uuid.UUID(user_id))
        if user is not None:
            user.pin_hash = pin_hash
            self._session.flush()


class SqlAlchemyRoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_id_by_key(self, role_key: str) -> str | None:
        role = self._session.scalars(select(Role).where(Role.key == role_key)).first()
        return str(role.id) if role else None


def _to_household_record(household: Household) -> HouseholdRecord:
    return HouseholdRecord(id=str(household.id), name=household.name, product_class=household.product_class)


def _to_user_record(user: User) -> UserRecord:
    return UserRecord(
        id=str(user.id),
        household_id=str(user.household_id),
        role_id=str(user.role_id),
        display_name=user.display_name,
        password_hash=user.password_hash,
        pin_hash=user.pin_hash,
    )


def _to_room_record(room: Room) -> RoomRecord:
    return RoomRecord(
        id=str(room.id),
        household_id=str(room.household_id),
        name=room.name,
        integration_id=str(room.integration_id) if room.integration_id else None,
        external_id=room.external_id,
    )


def _to_device_record(device: Device) -> DeviceRecord:
    return DeviceRecord(
        id=str(device.id),
        household_id=str(device.household_id),
        integration_id=str(device.integration_id),
        external_id=device.external_id,
        name=device.name,
        device_type=device.device_type,
        room_id=str(device.room_id) if device.room_id else None,
    )
