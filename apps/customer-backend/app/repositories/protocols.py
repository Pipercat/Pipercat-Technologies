"""Repository interfaces (S1V2-02-003). Structural Protocols, same
rationale as app/domain/adapter_port.py: services depend on these shapes,
never on SQLAlchemy directly, so unit tests can substitute in-memory fakes
(see tests/fakes.py) without a database."""

from typing import Protocol

from .records import DeviceRecord, RoomRecord, UserRecord


class RoomRepository(Protocol):
    def add(self, *, household_id: str, name: str) -> RoomRecord: ...

    def list_by_household(self, household_id: str) -> list[RoomRecord]: ...


class DeviceRepository(Protocol):
    def add(
        self, *, household_id: str, integration_id: str, external_id: str, name: str, device_type: str
    ) -> DeviceRecord: ...

    def get_by_external_id(self, integration_id: str, external_id: str) -> DeviceRecord | None: ...

    def list_by_household(self, household_id: str) -> list[DeviceRecord]: ...


class UserRepository(Protocol):
    def get_by_id(self, user_id: str) -> UserRecord | None: ...

    def get_permissions_for_role(self, role_id: str) -> frozenset[str]: ...
