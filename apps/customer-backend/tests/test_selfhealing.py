"""S1V2-02-006 Definition of Done: "Tests beweisen sichere Automatik und
Blockade riskanter Aktionen"."""

import pytest

from app.audit import InMemoryAuditRecorder
from app.events import InMemoryEventBus
from app.selfhealing import (
    ActionNotAllowedError,  # noqa: F401 - documents the exception type even though attempt() doesn't raise it
    EventBusAlertSink,
    InMemoryAlertSink,
    SAFE_ACTIONS,
    SelfHealAction,
    SelfHealingService,
    SelfHealOutcome,
    Severity,
    SystemIssue,
)


def _issue(component: str = "device_adapter", severity: Severity = Severity.WARNING) -> SystemIssue:
    return SystemIssue(component=component, severity=severity, message="adapter connection lost")


@pytest.fixture
def rig():
    audit = InMemoryAuditRecorder()
    alerts = InMemoryAlertSink()
    executed: list[SelfHealAction] = []

    async def succeeding_executor() -> bool:
        executed.append(SelfHealAction.RESTART_COMPONENT)
        return True

    async def failing_executor() -> bool:
        executed.append(SelfHealAction.RECONNECT_INTEGRATION)
        return False

    async def risky_executor_that_must_never_run() -> bool:
        executed.append(SelfHealAction.FACTORY_RESET)
        return True

    service = SelfHealingService(
        executors={
            SelfHealAction.RESTART_COMPONENT: succeeding_executor,
            SelfHealAction.RECONNECT_INTEGRATION: failing_executor,
            SelfHealAction.FACTORY_RESET: risky_executor_that_must_never_run,
        },
        audit=audit,
        alert_sink=alerts,
        alert_after_consecutive_failures=3,
    )
    return service, audit, alerts, executed


async def test_safe_action_executes_and_is_audited(rig):
    service, audit, _alerts, executed = rig
    issue = _issue()

    record = await service.attempt(issue, SelfHealAction.RESTART_COMPONENT)

    assert record.outcome == SelfHealOutcome.SUCCESS
    assert SelfHealAction.RESTART_COMPONENT in executed
    assert audit.events[-1]["action"] == "selfheal.restart_component"
    assert audit.events[-1]["outcome"] == "success"
    meta = audit.events[-1]["metadata"]
    assert meta["component"] == issue.component
    assert meta["trigger"] == issue.message
    assert meta["result"] == "success"


async def test_risky_action_is_blocked_and_executor_never_runs(rig):
    service, audit, _alerts, executed = rig
    issue = _issue(component="update_manager", severity=Severity.CRITICAL)
    assert SelfHealAction.FACTORY_RESET not in SAFE_ACTIONS

    record = await service.attempt(issue, SelfHealAction.FACTORY_RESET)

    assert record.outcome == SelfHealOutcome.BLOCKED_NOT_ALLOWLISTED
    assert SelfHealAction.FACTORY_RESET not in executed  # the risky executor was never called
    assert audit.events[-1]["action"] == "selfheal.factory_reset"
    assert audit.events[-1]["outcome"] == "failure"


async def test_every_risky_action_is_blocked():
    """All non-allowlisted actions are rejected, not just factory_reset."""
    audit = InMemoryAuditRecorder()
    alerts = InMemoryAlertSink()
    service = SelfHealingService(executors={}, audit=audit, alert_sink=alerts)

    for action in SelfHealAction:
        if action in SAFE_ACTIONS:
            continue
        record = await service.attempt(_issue(), action)
        assert record.outcome == SelfHealOutcome.BLOCKED_NOT_ALLOWLISTED


async def test_single_failure_does_not_alert_yet(rig):
    service, _audit, alerts, _executed = rig
    await service.attempt(_issue(), SelfHealAction.RECONNECT_INTEGRATION)
    assert alerts.alerts == []


async def test_repeated_failures_trigger_an_alert(rig):
    service, _audit, alerts, _executed = rig
    issue = _issue(component="ha_bridge")

    for _ in range(3):
        await service.attempt(issue, SelfHealAction.RECONNECT_INTEGRATION)

    assert len(alerts.alerts) == 1
    assert alerts.alerts[0]["component"] == "ha_bridge"
    assert alerts.alerts[0]["severity"] == Severity.CRITICAL


async def test_success_resets_the_failure_counter(rig):
    service, _audit, alerts, _executed = rig
    issue = _issue(component="mixed")

    await service.attempt(issue, SelfHealAction.RECONNECT_INTEGRATION)  # fail 1
    await service.attempt(issue, SelfHealAction.RECONNECT_INTEGRATION)  # fail 2
    await service.attempt(issue, SelfHealAction.RESTART_COMPONENT)  # success -> resets
    assert service.consecutive_failures("mixed") == 0

    await service.attempt(issue, SelfHealAction.RECONNECT_INTEGRATION)  # fail 1 again
    assert alerts.alerts == []  # never reached the threshold in one streak


async def test_broken_executor_is_treated_as_failure_not_a_crash(rig):
    service, audit, _alerts, _executed = rig

    async def boom() -> bool:
        raise RuntimeError("adapter socket closed")

    service._executors[SelfHealAction.CLEAR_CACHE] = boom
    record = await service.attempt(_issue(), SelfHealAction.CLEAR_CACHE)

    assert record.outcome == SelfHealOutcome.FAILED
    assert record.result_detail == "adapter socket closed"
    assert audit.events[-1]["outcome"] == "failure"


async def test_event_bus_alert_sink_publishes_a_system_alert_event():
    bus = InMemoryEventBus()
    published = []

    async def collect(event):
        published.append(event)

    await bus.subscribe(collect)
    sink = EventBusAlertSink(bus)

    await sink.alert(component="nas", severity=Severity.CRITICAL, message="disk full")

    assert len(published) == 1
    assert published[0].type == "system.alert"
    assert published[0].payload == {"component": "nas", "severity": "critical", "message": "disk full"}


async def test_history_reflects_all_attempts(rig):
    service, _audit, _alerts, _executed = rig
    issue = _issue(component="c1")
    await service.attempt(issue, SelfHealAction.RESTART_COMPONENT)
    await service.attempt(issue, SelfHealAction.RECONNECT_INTEGRATION)

    records = service.history(component="c1")
    assert len(records) == 2
    assert {r.outcome for r in records} == {SelfHealOutcome.SUCCESS, SelfHealOutcome.FAILED}
