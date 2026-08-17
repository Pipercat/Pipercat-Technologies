from fastapi.testclient import TestClient

from app.main import app

# raise_server_exceptions=False: this module deliberately triggers unhandled
# exceptions to verify the catch-all handler produces a safe response: with
# the default True, TestClient re-raises the original exception to the test
# even after a registered handler already produced a proper response.
client = TestClient(app, raise_server_exceptions=False)


def test_openapi_schema_is_served_and_documents_core_paths():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    for path in [
        "/api/v1/health",
        "/api/v1/features",
        "/api/v1/events/recent",
        "/api/v1/system/restart",
    ]:
        assert path in schema["paths"], f"{path} missing from generated OpenAPI schema"

    # Envelope + error models must be present so client generators can build
    # typed models from the schema (S1V2-01-004 Definition of Done).
    schemas = schema["components"]["schemas"]
    assert any(name.startswith("Envelope") for name in schemas)
    assert "ApiError" in schemas
    error_props = schemas["ApiError"]["properties"]
    assert set(error_props) >= {"code", "message", "correlationId"}


def test_error_responses_include_correlation_id_and_no_stack_trace(monkeypatch):
    monkeypatch.delenv("SYSTEMONE_PRODUCT_CLASS", raising=False)
    response = client.get("/api/v1/features")
    body = response.json()

    assert response.status_code == 500
    assert body["error"]["correlationId"]
    # The config-key name itself is not sensitive (it is already public in
    # infrastructure/docker-compose/.env.example) and is deliberately kept
    # in the message for operator diagnostics. What must never appear is a
    # stack trace or an actual secret value.
    assert "Traceback" not in response.text
    assert "File \"" not in response.text


def test_correlation_id_is_echoed_from_request_header():
    response = client.get(
        "/api/v1/health", headers={"X-Correlation-Id": "fixed-test-correlation-id"}
    )
    assert response.headers["X-Correlation-Id"] == "fixed-test-correlation-id"


def test_unhandled_exception_returns_generic_message_not_internal_detail(monkeypatch):
    """Simulates an unexpected server error and asserts the client never
    sees exception internals, per the 'keine Secrets/PII in Fehlern' rule."""

    def _boom():
        raise RuntimeError("super-secret-connection-string=postgresql://leak")

    monkeypatch.setattr("app.main.enabled_features", lambda _: _boom())
    monkeypatch.setenv("SYSTEMONE_PRODUCT_CLASS", "pi")

    response = client.get("/api/v1/features")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "super-secret-connection-string" not in response.text
