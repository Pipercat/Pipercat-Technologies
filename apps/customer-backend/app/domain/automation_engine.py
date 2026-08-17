"""Automation core engine (S1V2-02-005).

Only ever talks to devices through DeviceService (S1V2-02-002), never an
adapter directly - this is how "Verantwortung zwischen SystemONE und HA
kapseln" is satisfied: the engine has no idea whether a device is
simulated or, later, backed by Home Assistant.
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .automation_history import AutomationHistory, AutomationRun, AutomationRunOutcome
from .automation_types import Automation, DeviceStateCondition, DeviceStateTrigger, evaluate_comparison
from .capabilities import CapabilityType
from .device import DomainDevice
from .errors import CapabilityNotSupportedError, DeviceNotFoundError, TransientDeviceError
from .service import DeviceService

if TYPE_CHECKING:
    # app.events lives one level up (S1V2-01-004); the automation engine
    # only needs it for this one type hint, not as a runtime dependency.
    from app.events import DeviceStateEvent

logger = logging.getLogger("systemone.customer_backend.automation")

_MAX_ACTION_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 0.2


class AutomationValidationError(ValueError):
    def __init__(self, automation_id: str, errors: list[str]) -> None:
        super().__init__(f"Automation '{automation_id}' is invalid: {'; '.join(errors)}")
        self.automation_id = automation_id
        self.errors = errors


class AutomationEngine:
    def __init__(
        self,
        device_service: DeviceService,
        history: AutomationHistory,
        retry_delay_seconds: float = _RETRY_DELAY_SECONDS,
    ) -> None:
        self._device_service = device_service
        self._history = history
        self._retry_delay = retry_delay_seconds
        self._automations: dict[str, Automation] = {}
        self._last_time_trigger_minute: dict[str, str] = {}

    # --- registration -----------------------------------------------------

    async def register(self, automation: Automation) -> None:
        errors = await self.validate(automation)
        if errors:
            raise AutomationValidationError(automation.id, errors)
        self._automations[automation.id] = automation

    def unregister(self, automation_id: str) -> None:
        self._automations.pop(automation_id, None)

    async def validate(self, automation: Automation) -> list[str]:
        """"Validierung gegen Capabilities": every device_id/capability an
        automation references must actually exist and be supported."""
        errors: list[str] = []
        references: list[DeviceStateCondition] = list(automation.conditions)
        if isinstance(automation.trigger, DeviceStateTrigger):
            references.append(automation.trigger.condition)

        for condition in references:
            try:
                device = await self._device_service.get_device(condition.device_id)
            except DeviceNotFoundError:
                errors.append(f"device '{condition.device_id}' does not exist")
                continue
            if condition.capability not in device.capabilities:
                errors.append(f"device '{condition.device_id}' does not support '{condition.capability.value}'")

        for action in automation.actions:
            try:
                device = await self._device_service.get_device(action.device_id)
            except DeviceNotFoundError:
                errors.append(f"device '{action.device_id}' does not exist")
                continue
            if action.command.type not in device.capabilities:
                errors.append(f"device '{action.device_id}' does not support '{action.command.type.value}'")

        return errors

    # --- evaluation ---------------------------------------------------

    async def _condition_holds(self, condition: DeviceStateCondition) -> bool:
        device: DomainDevice = await self._device_service.get_device(condition.device_id)
        state = device.capabilities.get(condition.capability)
        if state is None:
            return False
        actual = getattr(state, condition.field, None)
        if actual is None:
            return False
        return evaluate_comparison(actual, condition.operator, condition.value)

    async def _all_conditions_hold(self, automation: Automation) -> bool:
        for condition in automation.conditions:
            if not await self._condition_holds(condition):
                return False
        return True

    # --- execution ----------------------------------------------------

    async def run(self, automation: Automation, *, reason: str) -> AutomationRun:
        if not automation.enabled:
            run = AutomationRun(
                automation_id=automation.id, trigger_reason=reason, outcome=AutomationRunOutcome.SKIPPED_DISABLED
            )
            self._history.record(run)
            return run

        if not await self._all_conditions_hold(automation):
            run = AutomationRun(
                automation_id=automation.id,
                trigger_reason=reason,
                outcome=AutomationRunOutcome.SKIPPED_CONDITIONS_NOT_MET,
            )
            self._history.record(run)
            return run

        attempts_used = 0
        try:
            for action in automation.actions:
                attempts_used = await self._execute_action_with_retry(action)
            run = AutomationRun(
                automation_id=automation.id,
                trigger_reason=reason,
                outcome=AutomationRunOutcome.SUCCESS,
                attempts=attempts_used,
            )
        except (DeviceNotFoundError, CapabilityNotSupportedError) as exc:
            # Permanent errors: never retried (see errors.py).
            run = AutomationRun(
                automation_id=automation.id,
                trigger_reason=reason,
                outcome=AutomationRunOutcome.FAILED,
                error_reason=str(exc),
                attempts=1,
            )
        except TransientDeviceError as exc:
            run = AutomationRun(
                automation_id=automation.id,
                trigger_reason=reason,
                outcome=AutomationRunOutcome.FAILED,
                error_reason=str(exc),
                attempts=_MAX_ACTION_ATTEMPTS,
            )
        self._history.record(run)
        if run.outcome == AutomationRunOutcome.FAILED:
            logger.warning("automation_run_failed automation_id=%s reason=%s", automation.id, run.error_reason)
        return run

    async def _execute_action_with_retry(self, action) -> int:
        last_error: TransientDeviceError | None = None
        for attempt in range(1, _MAX_ACTION_ATTEMPTS + 1):
            try:
                await self._device_service.send_command(action.device_id, action.command)
                return attempt
            except TransientDeviceError as exc:
                last_error = exc
                if attempt < _MAX_ACTION_ATTEMPTS:
                    await asyncio.sleep(self._retry_delay)
        assert last_error is not None
        raise last_error

    # --- triggers -------------------------------------------------------

    async def on_device_event(self, event: "DeviceStateEvent") -> list[AutomationRun]:
        runs = []
        for automation in list(self._automations.values()):
            trigger = automation.trigger
            if not isinstance(trigger, DeviceStateTrigger):
                continue
            if trigger.condition.device_id != event.payload.get("deviceId"):
                continue
            if await self._condition_holds(trigger.condition):
                runs.append(await self.run(automation, reason=f"device_event:{event.id}"))
        return runs

    async def check_time(self, now: datetime) -> list[AutomationRun]:
        """Idempotent per minute, mirroring the existing Node pilot's
        scheduler ("dieselbe Regel läuft höchstens einmal pro Minute")."""
        minute_key = now.strftime("%H:%M")
        date_key = now.strftime("%Y-%m-%d") + "T" + minute_key
        runs = []
        for automation in list(self._automations.values()):
            trigger = automation.trigger
            if trigger.type != "time" or trigger.at != minute_key:
                continue
            if self._last_time_trigger_minute.get(automation.id) == date_key:
                continue
            self._last_time_trigger_minute[automation.id] = date_key
            runs.append(await self.run(automation, reason=f"time:{minute_key}"))
        return runs

    async def check_sun_event(self, event: str, now: datetime) -> list[AutomationRun]:
        runs = []
        for automation in list(self._automations.values()):
            trigger = automation.trigger
            if trigger.type != "sun_event" or trigger.event != event:
                continue
            runs.append(await self.run(automation, reason=f"sun_event:{event}"))
        return runs

    def history(self, automation_id: str | None = None, limit: int = 50) -> list[AutomationRun]:
        if automation_id is not None:
            return self._history.for_automation(automation_id, limit=limit)
        return self._history.recent(limit=limit)
