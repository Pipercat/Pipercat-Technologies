"""Shared observability primitives (S1V2-01-005): structured logging with
correlation IDs + secret redaction, and a minimal metrics registry.

DEC-130, DEC-178-183. See docs/architecture/observability.md.
"""

import json
import logging
import re
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

# Redacts common secret-shaped substrings before anything reaches a log
# sink. Deliberately broad (false positives are cheap, leaked secrets are
# not) — mirrors the redaction philosophy already proven in the existing
# Node.js pilot (mvp/systemone-pi/lib/diagnostics.js).
_REDACTION_PATTERNS = [
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*[^\s,;]+"),
    re.compile(r"(?i)bearer\s+[a-z0-9\-_.]+"),
    re.compile(r"[a-z][a-z0-9+.-]*://[^:\s]+:[^@\s]+@"),  # user:pass@ in URLs
]


def redact(text: str) -> str:
    for pattern in _REDACTION_PATTERNS:
        text = pattern.sub(lambda m: _redact_match(m.group(0)), text)
    return text


def _redact_match(matched: str) -> str:
    if "://" in matched and matched.endswith("@"):
        scheme = matched.split("://", 1)[0]
        return f"{scheme}://[REDACTED]@"
    if matched.lower().startswith("bearer "):
        return "Bearer [REDACTED]"
    key = matched.split("=")[0] if "=" in matched else matched.split(":")[0]
    return f"{key}=[REDACTED]"


class CorrelationAndRedactionFilter(logging.Filter):
    """Injects correlationId/component onto every record and redacts the
    rendered message in place."""

    def __init__(self, component: str) -> None:
        super().__init__()
        self.component = component

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlationId = correlation_id_var.get()
        record.component = self.component
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", "unknown"),
            "correlationId": getattr(record, "correlationId", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            # Deliberately no traceback text here: exception details for
            # unexpected errors are logged separately by the catch-all
            # handler with just the exception type, never the full
            # exception message body, which could contain request data.
            payload["excType"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload)


def configure_logging(component: str, level: int = logging.INFO) -> None:
    """Call once at app startup. Never logs camera/audio payloads — those
    must not be routed through this logger at all (see
    docs/architecture/observability.md, "Kamera-/Audioinhalte")."""
    root = logging.getLogger("systemone")
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationAndRedactionFilter(component))
    root.addHandler(handler)
    root.propagate = False


# --- minimal metrics registry --------------------------------------------

MetricValue = int | float | str


class MetricsRegistry:
    """In-process gauge registry. Deliberately not a Prometheus client
    dependency yet — no scraping infrastructure exists to justify it
    (S1V2-01-005 decision). Subsystems that don't exist yet (DB, HA
    connection, backup/update) register their gauge function once they
    exist; nothing here hardcodes knowledge of them."""

    def __init__(self) -> None:
        self._gauges: dict[str, Callable[[], MetricValue]] = {}

    def register_gauge(self, name: str, fn: Callable[[], MetricValue]) -> None:
        self._gauges[name] = fn

    def snapshot(self) -> dict[str, MetricValue]:
        result: dict[str, MetricValue] = {}
        for name, fn in self._gauges.items():
            try:
                result[name] = fn()
            except Exception:  # a broken gauge must not break /metrics
                result[name] = "error"
        return result


metrics = MetricsRegistry()
