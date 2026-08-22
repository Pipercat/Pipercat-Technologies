"""S1V2-02-007 Definition of Done: "State-Machine-Tests inkl. Neustart
während Emergency; Zustand bleibt sicher und nachvollziehbar"."""

import pytest

from app.audit import InMemoryAuditRecorder
from app.authorization import AuthorizationError
from app.emergency import (
    EmergencyReasonCode,
    EmergencyState,
    EmergencyStateMachine,
    EmergencyStateSnapshot,
    EmergencyTransitionError,
)
from tests.fakes import make_actor


@pytest.fixture
def entry_log():
    return []


@pytest.fixture
def machine(entry_log):
    async def stop_services() -> bool:
        entry_log.append("stop_non_essential_services")
        return True

    async def restrict_access() -> bool:
        entry_log.append("restrict_access")
        return True

    async def protect_backups() -> bool:
        entry_log.append("protect_backups")
        return True

    audit = InMemoryAuditRecorder()
    actions = {
        "stop_non_essential_services": stop_services,
        "restrict_access": restrict_access,
        "protect_backups": protect_backups,
    }
    return EmergencyStateMachine(actions, audit), audit


async def test_manual_entry_reaches_emergency_and_runs_entry_actions(machine, entry_log):
    sm, audit = machine
    actor = make_actor("emergency:manage")

    await sm.enter_manually(actor, EmergencyReasonCode.MANUAL_LOCKDOWN)

    assert sm.state == EmergencyState.EMERGENCY
    assert entry_log == ["stop_non_essential_services", "restrict_access", "protect_backups"]
    actions_taken = [e["action"] for e in audit.events]
    assert actions_taken == ["emergency.entering", "emergency.entered"]


async def test_manual_entry_without_permission_is_denied(machine):
    sm, _audit = machine
    actor = make_actor()

    with pytest.raises(AuthorizationError):
        await sm.enter_manually(actor, EmergencyReasonCode.MANUAL_LOCKDOWN)
    assert sm.state == EmergencyState.NORMAL


async def test_automatic_entry_only_allowed_for_defined_danger_reasons(machine):
    sm, _audit = machine

    with pytest.raises(ValueError):
        await sm.enter_automatically(EmergencyReasonCode.MANUAL_LOCKDOWN)
    assert sm.state == EmergencyState.NORMAL

    await sm.enter_automatically(EmergencyReasonCode.SECURITY_INTRUSION_DETECTED)
    assert sm.state == EmergencyState.EMERGENCY


async def test_a_failing_entry_action_does_not_block_reaching_emergency():
    audit = InMemoryAuditRecorder()

    async def stop_services() -> bool:
        raise RuntimeError("systemd unavailable")

    async def restrict_access() -> bool:
        return True

    sm = EmergencyStateMachine(
        {"stop_non_essential_services": stop_services, "restrict_access": restrict_access}, audit
    )
    actor = make_actor("emergency:manage")

    await sm.enter_manually(actor, EmergencyReasonCode.SUSPECTED_THEFT)

    assert sm.state == EmergencyState.EMERGENCY  # fail-safe: still reaches EMERGENCY
    entered_event = next(e for e in audit.events if e["action"] == "emergency.entered")
    assert entered_event["metadata"]["entryActionResults"]["stop_non_essential_services"] is False
    assert entered_event["metadata"]["entryActionResults"]["restrict_access"] is True


async def test_automatic_recovery_when_clearly_safe(machine):
    sm, audit = machine
    actor = make_actor("emergency:manage")
    await sm.enter_manually(actor, EmergencyReasonCode.MANUAL_LOCKDOWN)
    await sm.begin_recovery(actor)

    async def definitely_safe() -> bool:
        return True

    result = await sm.attempt_automatic_recovery(definitely_safe)

    assert result == EmergencyState.NORMAL
    assert sm.state == EmergencyState.NORMAL
    assert audit.events[-1]["action"] == "emergency.recovered_automatically"


async def test_recovery_requires_human_approval_when_not_clearly_safe(machine):
    sm, audit = machine
    actor = make_actor("emergency:manage")
    await sm.enter_manually(actor, EmergencyReasonCode.MANUAL_LOCKDOWN)
    await sm.begin_recovery(actor)

    async def not_sure() -> bool:
        return False

    result = await sm.attempt_automatic_recovery(not_sure)
    assert result == EmergencyState.AWAITING_APPROVAL
    assert sm.state == EmergencyState.AWAITING_APPROVAL

    unauthorized = make_actor()
    with pytest.raises(AuthorizationError):
        await sm.approve_recovery(unauthorized)
    assert sm.state == EmergencyState.AWAITING_APPROVAL  # still not NORMAL

    await sm.approve_recovery(actor)
    assert sm.state == EmergencyState.NORMAL
    assert audit.events[-1]["action"] == "emergency.recovery_approved"


async def test_recovery_can_be_aborted_back_to_emergency(machine):
    sm, audit = machine
    actor = make_actor("emergency:manage")
    await sm.enter_manually(actor, EmergencyReasonCode.MANUAL_LOCKDOWN)
    await sm.begin_recovery(actor)

    await sm.recovery_failed_reenter_emergency(actor)

    assert sm.state == EmergencyState.EMERGENCY
    assert audit.events[-1]["action"] == "emergency.recovery_aborted"


async def test_invalid_transition_is_rejected(machine):
    sm, _audit = machine
    actor = make_actor("emergency:manage")

    with pytest.raises(EmergencyTransitionError):
        await sm.begin_recovery(actor)  # cannot recover from NORMAL
    assert sm.state == EmergencyState.NORMAL


async def test_restart_during_emergency_resumes_in_emergency_not_normal(entry_log):
    """The critical DoD scenario: a process restart while EMERGENCY is
    active must not silently forget the incident and fall back to NORMAL."""
    audit = InMemoryAuditRecorder()

    async def action() -> bool:
        return True

    actions = {"stop_non_essential_services": action, "restrict_access": action, "protect_backups": action}
    sm = EmergencyStateMachine(actions, audit)
    actor = make_actor("emergency:manage")
    await sm.enter_manually(actor, EmergencyReasonCode.SECURITY_INTRUSION_DETECTED)

    snapshot = sm.snapshot()
    assert snapshot.state == EmergencyState.EMERGENCY

    # Simulate a process restart: a fresh machine, reconstructed only from
    # the persisted snapshot (new audit recorder too, like a fresh process).
    fresh_audit = InMemoryAuditRecorder()
    resumed = EmergencyStateMachine.from_snapshot(snapshot, actions, fresh_audit)

    assert resumed.state == EmergencyState.EMERGENCY  # not reset to NORMAL
    assert resumed.snapshot().reason_code == EmergencyReasonCode.SECURITY_INTRUSION_DETECTED
    assert fresh_audit.events[-1]["action"] == "emergency.resumed_after_restart"
    assert fresh_audit.events[-1]["metadata"]["state"] == "emergency"


async def test_full_lifecycle_is_fully_audited(machine):
    sm, audit = machine
    actor = make_actor("emergency:manage")

    await sm.enter_manually(actor, EmergencyReasonCode.MANUAL_LOCKDOWN)
    await sm.begin_recovery(actor)
    await sm.approve_recovery(actor)

    actions_taken = [e["action"] for e in audit.events]
    assert actions_taken == [
        "emergency.entering",
        "emergency.entered",
        "emergency.recovery_started",
        "emergency.recovery_approved",
    ]
