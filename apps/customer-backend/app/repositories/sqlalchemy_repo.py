"""Real, PostgreSQL-backed repository implementations (S1V2-02-003).
Satisfy app.repositories.protocols structurally - no inheritance needed."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Device, Permission, Role, RolePermission, Room, User

from .records import DeviceRecord, RoomRecord, UserRecord


class SqlAlchemyRoomRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, household_id: str, name: str) -> RoomRecord:
        room = Room(household_id=uuid.UUID(household_id), name=name)
        self._session.add(room)
        self._session.flush()  # assigns room.id without committing the transaction
        return _to_room_record(room)

    def list_by_household(self, household_id: str) -> list[RoomRecord]:
        stmt = select(Room).where(Room.household_id == uuid.UUID(household_id), Room.deleted_at.is_(None))
        return [_to_room_record(r) for r in self._session.scalars(stmt)]


class SqlAlchemyDeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, *, household_id: str, integration_id: str, external_id: str, name: str, device_type: str
    ) -> DeviceRecord:
        device = Device(
            household_id=uuid.UUID(household_id),
            integration_id=uuid.UUID(integration_id),
            external_id=external_id,
            name=name,
            device_type=device_type,
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

    def list_by_household(self, household_id: str) -> list[DeviceRecord]:
        stmt = select(Device).where(Device.household_id == uuid.UUID(household_id), Device.deleted_at.is_(None))
        return [_to_device_record(d) for d in self._session.scalars(stmt)]


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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


class SqlAlchemyRoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_id_by_key(self, role_key: str) -> str | None:
        role = self._session.scalars(select(Role).where(Role.key == role_key)).first()
        return str(role.id) if role else None


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
    return RoomRecord(id=str(room.id), household_id=str(room.household_id), name=room.name)


def _to_device_record(device: Device) -> DeviceRecord:
    return DeviceRecord(
        id=str(device.id),
        household_id=str(device.household_id),
        integration_id=str(device.integration_id),
        external_id=device.external_id,
        name=device.name,
        device_type=device.device_type,
    )
