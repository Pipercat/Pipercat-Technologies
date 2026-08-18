"""Use-case layer for executing SystemONE device commands (S1V2-02-019).

Deliberately separate from `app.domain.service.DeviceService`, which
stays a pure domain orchestrator with no Actor/security concept at all
(S1V2-02-002's design). This is the security wrapper around it, mirroring
how `RoomService`/`DeviceRegistrationService` wrap repository access with
`require_permission` rather than putting authorization inside the
persistence layer itself.

"Capability- und Rechteprüfung vor Ausführung": `require_permission()`
runs first, then `DeviceService.send_command()` itself re-checks the
device actually has the requested capability (see service.py) - two
independent checks, neither trusting the other to have already run.

"Locks/Kameras bzw. sensible Aktionen durch Haushalts-PIN-Policy
schützen": commands touching LOCK or CAMERA_STREAM additionally go
through `ProtectedActionGuard.authorize_action()` (S1V2-02-012) - a
fresh PIN/biometric verification for *this* command specifically, never
cached across calls, exactly like every other protected action.
"""

from app.audit import AuditRecorder
from app.auth.protected_action import ProtectedActionGuard
from app.authorization import Actor, require_permission
from app.domain.capabilities import CapabilityCommand, CapabilityState
from app.domain.service import DeviceService

# Capability types whose commands are sensitive enough to require a
# fresh per-action PIN/biometric on top of the ordinary devices:control
# permission - a lock or a camera is a physical-security boundary, not
# just a convenience toggle like a light.
SENSITIVE_CAPABILITY_TYPES = {"lock", "camera_stream"}


class DeviceCommandService:
    def __init__(
        self, device_service: DeviceService, protected_action_guard: ProtectedActionGuard, audit: AuditRecorder
    ) -> None:
        self._device_service = device_service
        self._protected_action_guard = protected_action_guard
        self._audit = audit

    async def send_command(
        self,
        actor: Actor,
        *,
        device_id: str,
        command: CapabilityCommand,
        pin: str | None = None,
        biometric_assertion: str | None = None,
    ) -> CapabilityState:
        require_permission(actor, "devices:control")

        if command.type.value in SENSITIVE_CAPABILITY_TYPES:
            # Self-service: the actor proves it's still them, right now,
            # for this one command - not an admin unlocking someone
            # else's door. No unlock session exists here either, matching
            # ProtectedActionGuard's own "keine Freischaltsession" rule.
            await self._protected_action_guard.authorize_action(
                actor,
                target_user_id=actor.user_id,
                permission="devices:control",
                action=f"device.command.{command.type.value}",
                pin=pin,
                biometric_assertion=biometric_assertion,
            )

        try:
            new_state = await self._device_service.send_command(device_id, command)
        except Exception:
            self._audit.record(
                actor=actor,
                action="device.command_failed",
                target_type="device",
                target_id=device_id,
                outcome="failure",
                metadata={"capability": command.type.value},
            )
            raise

        self._audit.record(
            actor=actor,
            action="device.command_executed",
            target_type="device",
            target_id=device_id,
            outcome="success",
            metadata={"capability": command.type.value},
        )
        return new_state
