"""DeviceRegistrationService (S1V2-02-003).

Demonstrates the "idempotente Operationen" requirement concretely:
registering the same (integration_id, external_id) twice - e.g. because a
provisioning/import step was retried after a network error - returns the
existing registration instead of erroring or creating a duplicate. This is
the pattern later provisioning/remote/update services should follow, not
just this one use case.
"""

from collections.abc import Callable

from app.audit import AuditRecorder
from app.authorization import Actor, require_permission, require_same_household
from app.repositories.records import DeviceRecord
from app.uow import UnitOfWork


class DeviceRegistrationService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], audit: AuditRecorder) -> None:
        self._uow_factory = uow_factory
        self._audit = audit

    def register_device(
        self,
        actor: Actor,
        *,
        household_id: str,
        integration_id: str,
        external_id: str,
        name: str,
        device_type: str,
    ) -> DeviceRecord:
        require_permission(actor, "devices:manage")
        require_same_household(actor, household_id)

        with self._uow_factory() as uow:
            existing = uow.devices.get_by_external_id(integration_id, external_id)
            if existing is not None:
                uow.commit()
                self._audit.record(
                    actor=actor,
                    action="device.registration_replayed",
                    target_type="device",
                    target_id=existing.id,
                    outcome="success",
                    metadata={"idempotent": True},
                )
                return existing

            device = uow.devices.add(
                household_id=household_id,
                integration_id=integration_id,
                external_id=external_id,
                name=name,
                device_type=device_type,
            )
            uow.commit()

        self._audit.record(
            actor=actor,
            action="device.registered",
            target_type="device",
            target_id=device.id,
            outcome="success",
        )
        return device
