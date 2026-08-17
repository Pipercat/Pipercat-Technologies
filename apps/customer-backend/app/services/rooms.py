"""RoomService: the first use-case service (S1V2-02-003). Deliberately
thin API routes will call these methods rather than touching repositories/
the ORM directly (see docs/architecture/service-repository-layer.md)."""

from collections.abc import Callable

from app.audit import AuditRecorder
from app.authorization import Actor, require_permission
from app.repositories.records import RoomRecord
from app.uow import UnitOfWork


class RoomService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], audit: AuditRecorder) -> None:
        self._uow_factory = uow_factory
        self._audit = audit

    def create_room(self, actor: Actor, *, household_id: str, name: str) -> RoomRecord:
        require_permission(actor, "rooms:manage")
        with self._uow_factory() as uow:
            room = uow.rooms.add(household_id=household_id, name=name)
            uow.commit()
        self._audit.record(
            actor=actor, action="room.created", target_type="room", target_id=room.id, outcome="success"
        )
        return room

    def list_rooms(self, actor: Actor, *, household_id: str) -> list[RoomRecord]:
        require_permission(actor, "rooms:read")
        with self._uow_factory() as uow:
            return uow.rooms.list_by_household(household_id)
