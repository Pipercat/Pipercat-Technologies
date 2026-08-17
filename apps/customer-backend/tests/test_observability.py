import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import redact

client = TestClient(app, raise_server_exceptions=False)


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


@pytest.fixture
def captured_logs():
    """Attaches directly to the 'systemone' logger (which has
    propagate=False, see app/observability.py) rather than relying on
    pytest's caplog + root-logger propagation, which the disabled
    propagation deliberately bypasses."""
    handler = _ListHandler()
    handler.setFormatter(logging.getLogger("systemone").handlers[0].formatter)
    logger = logging.getLogger("systemone")
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


@pytest.mark.parametrize(
    "raw,expected_hidden",
    [
        ("password=hunter2", "hunter2"),
        ("token: abcdef123456", "abcdef123456"),
        ("Authorization: Bearer eyJhbGciOi.abc.def", "eyJhbGciOi.abc.def"),
        ("postgresql://systemone:supersecret@postgres:5432/db", "supersecret"),
    ],
)
def test_redact_hides_secret_shaped_values(raw, expected_hidden):
    assert expected_hidden not in redact(raw)


def test_health_live_and_ready(monkeypatch):
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")
    for path in ["/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"


def test_metrics_snapshot_includes_registered_gauges():
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    values = response.json()["data"]["values"]
    assert "events_in_memory" in values
    assert "idempotency_keys_cached" in values


def test_end_to_end_correlation_id_flows_into_logs(captured_logs, monkeypatch):
    monkeypatch.delenv("SYSTEMONE_PRODUCT_CLASS", raising=False)

    response = client.get(
        "/api/v1/features", headers={"X-Correlation-Id": "trace-through-the-stack"}
    )
    assert response.status_code == 500
    assert response.headers["X-Correlation-Id"] == "trace-through-the-stack"

    parsed = [json.loads(line) for line in captured_logs.records]
    assert any(entry["correlationId"] == "trace-through-the-stack" for entry in parsed)
    assert all(entry["component"] == "customer-backend" for entry in parsed)


def test_redaction_filter_applies_to_real_log_records(captured_logs):
    """Exercises the actual logging.Filter wired up in configure_logging(),
    not just the pure redact() function, per the DoD requirement that
    secret redaction is automatically tested end-to-end."""
    logger = logging.getLogger("systemone.customer_backend")
    logger.warning("connecting with password=do-not-leak-this")

    combined = "\n".join(captured_logs.records)
    assert "do-not-leak-this" not in combined
    assert "[REDACTED]" in combined


def test_logs_never_contain_leaked_secret(captured_logs, monkeypatch):
    monkeypatch.setattr(
        "app.main.enabled_features",
        lambda _: (_ for _ in ()).throw(RuntimeError("password=do-not-log-me")),
    )
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")

    client.get("/api/v1/features")

    combined = "\n".join(captured_logs.records)
    assert "do-not-log-me" not in combined
