import pytest

from app import events, idempotency, main


@pytest.fixture(autouse=True)
def reset_module_state():
    """The demo endpoints in app/main.py intentionally use simple in-memory
    module-level state (real persistence is S1V2-02-001). Reset it before
    every test so tests stay independent of execution order."""
    main._system_state["version"] = 1
    idempotency.idempotency_store._store.clear()
    events.event_bus._events.clear()
    yield
