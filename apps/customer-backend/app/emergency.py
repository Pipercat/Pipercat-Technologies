"""Emergency-mode state machine for severe incidents (S1V2-02-007).

DEC-184..190: for severe disruptions or security incidents, non-essential
services may be stopped in a controlled way, access restricted, and
backups specially protected; only functions needed for analysis,
containment and recovery stay active.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field

from .audit import AuditRecorder
from .authorization import Actor, require_permission


class EmergencyState(str, Enum):
    NORMAL = "normal"
    ENTERING_EMERGENCY = "entering_emergency"
    EMERGENCY = "emergency"
    RECOVERING = "recovering"
    AWAITING_APPROVAL = "awaiting_approval"


class EmergencyReasonCode(str, Enum):
    # Automatic entry is only ever allowed for these "eindeutig definierte
    # Gefahrzustände" - anything else needs a human to press the button.
    SECURITY_INTRUSION_DETECTED = "security_intrusion_detected"
    STORAGE_CORRUPTION_DETECTED = "storage_corruption_detected"
    CRITICAL_SELF_HEAL_EXHAUSTED = "critical_self_heal_exhausted"
    # Manual-only reasons (owner/administrator judgment call).
    MANUAL_LOCKDOWN = "manual_lockdown"
    SUSPECTED_THEFT = "suspected_theft"


AUTOMATIC_ENTRY_REASONS: frozenset[EmergencyReasonCode] = frozenset(
    {
        EmergencyReasonCode.SECURITY_INTRUSION_DETECTED,
        EmergencyReasonCode.STORAGE_CORRUPTION_DETECTED,
        EmergencyReasonCode.CRITICAL_SELF_HEAL_EXHAUSTED,
    }
)


class EmergencyTransitionError(RuntimeError):
    def __init__(self, from_state: EmergencyState, to_state: EmergencyState) -> None:
        super().__init__(f"Cannot transition from '{from_state.value}' to '{to_state.value}'")
        self.from_state = from_state
        self.to_state = to_state


ALLOWED_TRANSITIONS: dict[EmergencyState, frozenset[EmergencyState]] = {
    EmergencyState.NORMAL: frozenset({EmergencyState.ENTERING_EMERGENCY}),
    EmergencyState.ENTERING_EMERGENCY: frozenset({EmergencyState.EMERGENCY}),
    EmergencyState.EMERGENCY: frozenset({EmergencyState.RECOVERING}),
    EmergencyState.RECOVERING: frozenset(
        {EmergencyState.NORMAL, EmergencyState.AWAITING_APPROVAL, EmergencyState.EMERGENCY}
    ),
    EmergencyState.AWAITING_APPROVAL: frozenset({EmergencyState.NORMAL, EmergencyState.EMERGENCY}),
}


class EmergencyStateSnapshot(BaseModel):
    """Serializable state, so a process restart during EMERGENCY resumes
    safely instead of silently forgetting the incident (S1V2-02-007 DoD:
    "Neustart während Emergency; Zustand bleibt sicher und
    nachvollziehbar")."""

    state: EmergencyState
    reason_code: EmergencyReasonCode | None = None
    entered_at: datetime | None = None


class EntryAction(Protocol):
    async def __call__(self) -> bool: ...


class SafetyCheck(Protocol):
    async def __call__(self) -> bool:
        """Returns True only if recovery to NORMAL is unambiguously safe."""
        ...


class EmergencyStateMachine:
    def __init__(
        self,
        entry_actions: dict[str, EntryAction],
        audit: AuditRecorder,
        snapshot: EmergencyStateSnapshot | None = None,
    ) -> None:
        self._entry_actions = entry_actions
        self._audit = audit
        snapshot = snapshot or EmergencyStateSnapshot(state=EmergencyState.NORMAL)
        self._state = snapshot.state
        self._reason_code = snapshot.reason_code
        self._entered_at = snapshot.entered_at
        self._entry_action_results: dict[str, bool] = {}

    @classmethod
    def from_snapshot(
        cls, snapshot: EmergencyStateSnapshot, entry_actions: dict[str, EntryAction], audit: AuditRecorder
    ) -> "EmergencyStateMachine":
        """Reconstructs a machine after a restart. Resuming into EMERGENCY
        (rather than defaulting to NORMAL) is exactly the safety property
        this task requires."""
        machine = cls(entry_actions, audit, snapshot=snapshot)
        audit.record(
            actor=None,
            action="emergency.resumed_after_restart",
            target_type="system",
            target_id=None,
            outcome="success",
            metadata={"state": snapshot.state.value, "reasonCode": snapshot.reason_code.value if snapshot.reason_code else None},
        )
        return machine

    @property
    def state(self) -> EmergencyState:
        return self._state

    def snapshot(self) -> EmergencyStateSnapshot:
        return EmergencyStateSnapshot(state=self._state, reason_code=self._reason_code, entered_at=self._entered_at)

    def _assert_transition_allowed(self, to_state: EmergencyState) -> None:
        if to_state not in ALLOWED_TRANSITIONS[self._state]:
            raise EmergencyTransitionError(self._state, to_state)

    def _transition(self, to_state: EmergencyState) -> None:
        self._assert_transition_allowed(to_state)
        self._state = to_state

    def _audit_transition(self, action: str, actor: Actor | None, **metadata) -> None:
        self._audit.record(
            actor=actor, action=action, target_type="system", target_id=None, outcome="success", metadata=metadata
        )

    # --- entry --------------------------------------------------------

    async def enter_manually(self, actor: Actor, reason_code: EmergencyReasonCode) -> None:
        require_permission(actor, "emergency:manage")
        await self._enter(reason_code, triggered_by="manual", actor=actor)

    async def enter_automatically(self, reason_code: EmergencyReasonCode) -> None:
        if reason_code not in AUTOMATIC_ENTRY_REASONS:
            raise ValueError(
                f"'{reason_code.value}' is not an allowed automatic-entry reason; "
                "this requires a human decision (enter_manually)."
            )
        await self._enter(reason_code, triggered_by="automatic", actor=None)

    async def _enter(self, reason_code: EmergencyReasonCode, *, triggered_by: str, actor: Actor | None) -> None:
        self._transition(EmergencyState.ENTERING_EMERGENCY)
        self._reason_code = reason_code
        self._entered_at = datetime.now(UTC)
        self._audit_transition(
            "emergency.entering", actor, reasonCode=reason_code.value, triggeredBy=triggered_by
        )

        self._entry_action_results = {}
        for name, action in self._entry_actions.items():
            try:
                self._entry_action_results[name] = await action()
            except Exception:
                # Fail-safe, not fail-closed-in-limbo: one broken entry
                # action (e.g. "stop non-essential service X" failing)
                # must not prevent reaching the safe EMERGENCY state.
                self._entry_action_results[name] = False

        self._transition(EmergencyState.EMERGENCY)
        self._audit_transition(
            "emergency.entered",
            actor,
            reasonCode=reason_code.value,
            triggeredBy=triggered_by,
            entryActionResults=self._entry_action_results,
        )

    # --- recovery -------------------------------------------------------

    async def begin_recovery(self, actor: Actor) -> None:
        require_permission(actor, "emergency:manage")
        self._transition(EmergencyState.RECOVERING)
        self._audit_transition("emergency.recovery_started", actor)

    async def attempt_automatic_recovery(self, safety_check: SafetyCheck) -> EmergencyState:
        """Automatische Rückkehr nur, wenn eindeutig sicher; sonst Freigabe
        durch eine berechtigte Person nötig."""
        if self._state != EmergencyState.RECOVERING:
            raise EmergencyTransitionError(self._state, EmergencyState.NORMAL)

        is_safe = await safety_check()
        if is_safe:
            self._transition(EmergencyState.NORMAL)
            self._reason_code = None
            self._entered_at = None
            self._audit_transition("emergency.recovered_automatically", actor=None)
        else:
            self._transition(EmergencyState.AWAITING_APPROVAL)
            self._audit_transition("emergency.awaiting_approval", actor=None)
        return self._state

    async def approve_recovery(self, actor: Actor) -> None:
        require_permission(actor, "emergency:manage")
        self._transition(EmergencyState.NORMAL)
        self._reason_code = None
        self._entered_at = None
        self._audit_transition("emergency.recovery_approved", actor)

    async def recovery_failed_reenter_emergency(self, actor: Actor | None = None) -> None:
        """Recovery turned out to be unsafe after all - back to EMERGENCY,
        never silently to NORMAL."""
        self._transition(EmergencyState.EMERGENCY)
        self._audit_transition("emergency.recovery_aborted", actor)
