"""System status / error / safe self-healing service (S1V2-02-006).

Deliberately at the app/ top level, not app/domain/: this coordinates
audit (app/audit.py) and alerting (via the EventBus port from
S1V2-01-004/-02-004), which are cross-cutting concerns, not pure device
domain logic.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field

from .audit import AuditRecorder
from .authorization import Actor

# --- severity / issues -----------------------------------------------------


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SystemIssue(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component: str
    severity: Severity
    message: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- actions: the allowlist is the whole point of this module --------------


class SelfHealAction(str, Enum):
    # Safe: local, reversible, no data loss, no security posture change.
    RESTART_COMPONENT = "restart_component"
    CLEAR_CACHE = "clear_cache"
    RECONNECT_INTEGRATION = "reconnect_integration"
    RESTART_DEVICE_ADAPTER = "restart_device_adapter"
    # Risky: destructive, irreversible, or security-relevant. Never
    # executed automatically, regardless of what a caller requests -
    # SAFE_ACTIONS is the single source of truth, checked in code, not
    # just documented.
    FACTORY_RESET = "factory_reset"
    DELETE_ALL_DATA = "delete_all_data"
    DISABLE_TLS = "disable_tls"
    INSTALL_UPDATE = "install_update"  # updates require explicit customer approval (product-manifest.md §6)


SAFE_ACTIONS: frozenset[SelfHealAction] = frozenset(
    {
        SelfHealAction.RESTART_COMPONENT,
        SelfHealAction.CLEAR_CACHE,
        SelfHealAction.RECONNECT_INTEGRATION,
        SelfHealAction.RESTART_DEVICE_ADAPTER,
    }
)


class ActionExecutor(Protocol):
    async def __call__(self) -> bool:
        """Returns True on success. May raise; a raised exception is
        treated as failure, not propagated to the caller of attempt()."""
        ...


class AlertSink(Protocol):
    async def alert(self, *, component: str, severity: Severity, message: str) -> None: ...


class InMemoryAlertSink:
    def __init__(self) -> None:
        self.alerts: list[dict] = []

    async def alert(self, *, component: str, severity: Severity, message: str) -> None:
        self.alerts.append({"component": component, "severity": severity, "message": message})


class EventBusAlertSink:
    """Production alert sink: publishes onto the existing EventBus
    (S1V2-01-004/-02-004) instead of inventing a second notification
    channel."""

    def __init__(self, event_bus) -> None:
        self._event_bus = event_bus

    async def alert(self, *, component: str, severity: Severity, message: str) -> None:
        from .events import DeviceStateEvent

        await self._event_bus.publish(
            DeviceStateEvent(
                type="system.alert",
                payload={"component": component, "severity": severity.value, "message": message},
            )
        )


# --- outcomes / history -----------------------------------------------------


class SelfHealOutcome(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED_NOT_ALLOWLISTED = "blocked_not_allowlisted"


class SelfHealRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: str
    component: str
    action: SelfHealAction
    trigger: str
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    outcome: SelfHealOutcome
    result_detail: str | None = None


class ActionNotAllowedError(PermissionError):
    def __init__(self, action: SelfHealAction) -> None:
        super().__init__(
            f"Self-healing action '{action.value}' is not in the safe allowlist; "
            "it requires explicit human action, not automatic execution."
        )
        self.action = action


# --- service ----------------------------------------------------------------

_ALERT_AFTER_CONSECUTIVE_FAILURES = 3


class SelfHealingService:
    def __init__(
        self,
        executors: dict[SelfHealAction, ActionExecutor],
        audit: AuditRecorder,
        alert_sink: AlertSink,
        alert_after_consecutive_failures: int = _ALERT_AFTER_CONSECUTIVE_FAILURES,
    ) -> None:
        self._executors = executors
        self._audit = audit
        self._alert_sink = alert_sink
        self._alert_threshold = alert_after_consecutive_failures
        self._history: list[SelfHealRecord] = []
        self._consecutive_failures: dict[str, int] = defaultdict(int)

    async def attempt(self, issue: SystemIssue, action: SelfHealAction, *, actor: Actor | None = None) -> SelfHealRecord:
        """Never raises for a blocked/failed action - the *record*
        expresses the outcome, so callers cannot accidentally treat "we
        declined to act" as an unhandled exception."""
        if action not in SAFE_ACTIONS:
            record = SelfHealRecord(
                issue_id=issue.id,
                component=issue.component,
                action=action,
                trigger=issue.message,
                outcome=SelfHealOutcome.BLOCKED_NOT_ALLOWLISTED,
                result_detail="Action requires explicit human approval, not in safe allowlist.",
            )
            self._record(record, actor, outcome="failure")
            return record

        executor = self._executors.get(action)
        success = False
        detail: str | None = None
        if executor is None:
            detail = "No executor registered for this action."
        else:
            try:
                success = await executor()
            except Exception as exc:  # a broken executor must not crash the health service
                detail = str(exc)

        outcome = SelfHealOutcome.SUCCESS if success else SelfHealOutcome.FAILED
        record = SelfHealRecord(
            issue_id=issue.id,
            component=issue.component,
            action=action,
            trigger=issue.message,
            outcome=outcome,
            result_detail=detail,
        )
        self._record(record, actor, outcome="success" if success else "failure")

        if success:
            self._consecutive_failures[issue.component] = 0
        else:
            self._consecutive_failures[issue.component] += 1
            if self._consecutive_failures[issue.component] >= self._alert_threshold:
                await self._alert_sink.alert(
                    component=issue.component,
                    severity=Severity.CRITICAL,
                    message=(
                        f"Self-healing action '{action.value}' failed "
                        f"{self._consecutive_failures[issue.component]} times in a row for "
                        f"'{issue.component}'."
                    ),
                )
        return record

    def _record(self, record: SelfHealRecord, actor: Actor | None, *, outcome: str) -> None:
        self._history.append(record)
        # "jede automatische Aktion mit Trigger/Zeit/Komponente/Aktion/
        # Ergebnis auditieren" - all five are in the AuditEvent metadata.
        self._audit.record(
            actor=actor,
            action=f"selfheal.{record.action.value}",
            target_type="component",
            target_id=None,
            outcome=outcome,
            metadata={
                "trigger": record.trigger,
                "component": record.component,
                "issueId": record.issue_id,
                "result": record.outcome.value,
                "triggeredAt": record.triggered_at.isoformat(),
            },
        )

    def history(self, component: str | None = None, limit: int = 50) -> list[SelfHealRecord]:
        records = self._history if component is None else [r for r in self._history if r.component == component]
        return list(reversed(records))[:limit]

    def consecutive_failures(self, component: str) -> int:
        return self._consecutive_failures[component]
