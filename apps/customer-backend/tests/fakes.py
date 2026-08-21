"""In-memory fakes for the repository/UoW/audit ports (S1V2-02-003
Definition of Done: "Unit-Tests prüfen Services mit Fake-Repositories").
No database, no SQLAlchemy import anywhere in this file.
"""

import uuid

from app.audit import InMemoryAuditRecorder
from app.repositories.records import DeviceRecord, HouseholdRecord, RoomRecord, UserRecord


class FakeRoomRepository:
    def __init__(self) -> None:
        self._rooms: dict[str, RoomRecord] = {}

    def add(
        self, *, household_id: str, name: str, integration_id: str | None = None, external_id: str | None = None
    ) -> RoomRecord:
        room = RoomRecord(
            id=str(uuid.uuid4()),
            household_id=household_id,
            name=name,
            integration_id=integration_id,
            external_id=external_id,
        )
        self._rooms[room.id] = room
        return room

    def get_by_external_id(self, integration_id: str, external_id: str) -> RoomRecord | None:
        for room in self._rooms.values():
            if room.integration_id == integration_id and room.external_id == external_id:
                return room
        return None

    def update_name(self, room_id: str, name: str) -> None:
        existing = self._rooms.get(room_id)
        if existing is not None:
            self._rooms[room_id] = RoomRecord(
                id=existing.id,
                household_id=existing.household_id,
                name=name,
                integration_id=existing.integration_id,
                external_id=existing.external_id,
            )

    def list_by_household(self, household_id: str) -> list[RoomRecord]:
        return [r for r in self._rooms.values() if r.household_id == household_id]


class FakeDeviceRepository:
    def __init__(self) -> None:
        self._devices: dict[str, DeviceRecord] = {}

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
        device = DeviceRecord(
            id=str(uuid.uuid4()),
            household_id=household_id,
            integration_id=integration_id,
            external_id=external_id,
            name=name,
            device_type=device_type,
            room_id=room_id,
        )
        self._devices[device.id] = device
        return device

    def get_by_external_id(self, integration_id: str, external_id: str) -> DeviceRecord | None:
        for device in self._devices.values():
            if device.integration_id == integration_id and device.external_id == external_id:
                return device
        return None

    def update(self, device_id: str, *, name: str, room_id: str | None) -> None:
        existing = self._devices.get(device_id)
        if existing is not None:
            self._devices[device_id] = DeviceRecord(
                id=existing.id,
                household_id=existing.household_id,
                integration_id=existing.integration_id,
                external_id=existing.external_id,
                name=name,
                device_type=existing.device_type,
                room_id=room_id,
            )

    def list_by_household(self, household_id: str) -> list[DeviceRecord]:
        return [d for d in self._devices.values() if d.household_id == household_id]


class FakeUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._role_permissions: dict[str, frozenset[str]] = {}

    def seed(self, user: UserRecord) -> None:
        """Test-only convenience for pre-populating a fully-formed user -
        not part of the real UserRepository protocol (see `add()` below
        for that)."""
        self._users[user.id] = user

    def add(
        self,
        *,
        household_id: str,
        role_id: str,
        display_name: str,
        password_hash: str | None = None,
        pin_hash: str | None = None,
    ) -> UserRecord:
        user = UserRecord(
            id=str(uuid.uuid4()),
            household_id=household_id,
            role_id=role_id,
            display_name=display_name,
            password_hash=password_hash,
            pin_hash=pin_hash,
        )
        self._users[user.id] = user
        return user

    def set_role_permissions(self, role_id: str, permissions: frozenset[str]) -> None:
        self._role_permissions[role_id] = permissions

    def get_by_id(self, user_id: str) -> UserRecord | None:
        return self._users.get(user_id)

    def get_permissions_for_role(self, role_id: str) -> frozenset[str]:
        return self._role_permissions.get(role_id, frozenset())

    def set_role(self, user_id: str, role_id: str) -> None:
        existing = self._users.get(user_id)
        if existing is not None:
            self._users[user_id] = UserRecord(
                id=existing.id,
                household_id=existing.household_id,
                role_id=role_id,
                display_name=existing.display_name,
                password_hash=existing.password_hash,
                pin_hash=existing.pin_hash,
            )

    def set_pin_hash(self, user_id: str, pin_hash: str | None) -> None:
        existing = self._users.get(user_id)
        if existing is not None:
            self._users[user_id] = UserRecord(
                id=existing.id,
                household_id=existing.household_id,
                role_id=existing.role_id,
                display_name=existing.display_name,
                password_hash=existing.password_hash,
                pin_hash=pin_hash,
            )


class FakeHouseholdRepository:
    def __init__(self) -> None:
        self._households: dict[str, HouseholdRecord] = {}

    def add(self, *, name: str, product_class: str) -> HouseholdRecord:
        household = HouseholdRecord(id=str(uuid.uuid4()), name=name, product_class=product_class)
        self._households[household.id] = household
        return household

    def get_by_id(self, household_id: str) -> HouseholdRecord | None:
        return self._households.get(household_id)

    def all(self) -> list[HouseholdRecord]:
        """Test-only introspection, not part of HouseholdRepository's
        protocol - lets a test assert "no new household was created"
        without reaching into a private attribute."""
        return list(self._households.values())


class FakeRoleRepository:
    def __init__(self) -> None:
        self._role_ids_by_key: dict[str, str] = {}

    def add(self, role_key: str, role_id: str) -> None:
        self._role_ids_by_key[role_key] = role_id

    def get_id_by_key(self, role_key: str) -> str | None:
        return self._role_ids_by_key.get(role_key)


class FakeUnitOfWork:
    """committed/rolled_back flags let tests assert transaction discipline
    without a real database."""

    def __init__(self) -> None:
        self.rooms = FakeRoomRepository()
        self.devices = FakeDeviceRepository()
        self.users = FakeUserRepository()
        self.roles = FakeRoleRepository()
        self.households = FakeHouseholdRepository()
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


DEFAULT_TEST_HOUSEHOLD_ID = "hh-1"  # matches the household_id="hh-1" convention already used throughout tests/


def make_actor(*permissions: str, household_id: str = DEFAULT_TEST_HOUSEHOLD_ID) -> "Actor":
    from app.authorization import Actor

    return Actor(user_id=str(uuid.uuid4()), household_id=household_id, permissions=frozenset(permissions))


__all__ = [
    "FakeRoomRepository",
    "FakeDeviceRepository",
    "FakeUserRepository",
    "FakeRoleRepository",
    "FakeHouseholdRepository",
    "FakeUnitOfWork",
    "InMemoryAuditRecorder",
    "make_actor",
]
