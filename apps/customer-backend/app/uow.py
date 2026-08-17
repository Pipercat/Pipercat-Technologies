"""Unit of Work (S1V2-02-003): one transaction per use case, spanning
however many repository writes belong together ("Transaktionen für
zusammengehörige Änderungen"). Services depend on the `UnitOfWork`
Protocol, never on a SQLAlchemy Session directly."""

from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from app.repositories.protocols import DeviceRepository, RoleRepository, RoomRepository, UserRepository
from app.repositories.sqlalchemy_repo import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyRoomRepository,
    SqlAlchemyUserRepository,
)


class UnitOfWork(Protocol):
    rooms: RoomRepository
    devices: DeviceRepository
    users: UserRepository
    roles: RoleRepository

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, exc_type, exc, tb) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.rooms = SqlAlchemyRoomRepository(self.session)
        self.devices = SqlAlchemyDeviceRepository(self.session)
        self.users = SqlAlchemyUserRepository(self.session)
        self.roles = SqlAlchemyRoleRepository(self.session)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.session is not None
        if exc_type is not None:
            self.rollback()
        self.session.close()

    def commit(self) -> None:
        assert self.session is not None
        self.session.commit()

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()
