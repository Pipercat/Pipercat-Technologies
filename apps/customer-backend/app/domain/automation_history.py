"""Execution history (S1V2-02-005: "Ausführungshistorie, Fehlergrund").

In-memory only for now, same deliberate scope boundary as the rest of the
domain layer (S1V2-02-002): persisting Automation/AutomationRun rows to
PostgreSQL is a natural follow-up through the Service/Repository layer
(S1V2-02-003's pattern), not this task - keeps the core model testable
without a database, consistent with how DomainDevice was built.
"""

import uuid
from collections import deque
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class AutomationRunOutcome(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED_DISABLED = "skipped_disabled"
    SKIPPED_CONDITIONS_NOT_MET = "skipped_conditions_not_met"


class AutomationRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    automation_id: str
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trigger_reason: str
    outcome: AutomationRunOutcome
    error_reason: str | None = None
    attempts: int = 1


class AutomationHistory:
    _MAX_RETAINED = 500

    def __init__(self) -> None:
        self._runs: deque[AutomationRun] = deque(maxlen=self._MAX_RETAINED)

    def record(self, run: AutomationRun) -> None:
        self._runs.append(run)

    def for_automation(self, automation_id: str, limit: int = 50) -> list[AutomationRun]:
        matching = [r for r in reversed(self._runs) if r.automation_id == automation_id]
        return matching[:limit]

    def recent(self, limit: int = 50) -> list[AutomationRun]:
        return list(reversed(self._runs))[:limit]
