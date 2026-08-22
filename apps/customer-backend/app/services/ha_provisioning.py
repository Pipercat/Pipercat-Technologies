"""Builds a real `HomeAssistantAdapter` from stored integration
credentials (S1V2-02-021).

Closes a gap explicitly flagged as deferred in `docs/architecture/
home-assistant-adapter.md` and `docs/architecture/secrets-management.md`:
`SecretStore` (S1V2-02-013) has always been able to store a Home
Assistant long-lived access token, but nothing in `apps/customer-backend`
ever actually read it back to construct a working adapter - every real
`HomeAssistantAdapter` in the codebase so far has been built directly by
a test or by `ha_conftest.py`'s onboarding flow, never from persisted
household configuration.

Returns `None` (never raises) when no credential is configured yet -
"not yet onboarded" is an expected, ordinary state for a fresh household,
not an error condition. Local-first (`docs/product-manifest.md` §2)
requires SystemONE to run without Home Assistant reachable at every
process start, so callers must treat a `None` result as "fall back to
whatever adapter is appropriate" rather than fail.
"""

from home_assistant_adapter import HomeAssistantAdapter

from app.secret_store import SecretNotFoundError, SecretStore
from app.services.ha_device_adapter import TranslatingHomeAssistantAdapter

HOME_ASSISTANT_ACCESS_TOKEN_SECRET_KEY = "long_lived_access_token"


def build_home_assistant_adapter(
    secret_store: SecretStore, *, integration_id: str, base_url: str, timeout_seconds: float = 10.0
) -> HomeAssistantAdapter | None:
    if not secret_store.has_secret(integration_id=integration_id, key=HOME_ASSISTANT_ACCESS_TOKEN_SECRET_KEY):
        return None
    try:
        access_token = secret_store.get_secret(integration_id=integration_id, key=HOME_ASSISTANT_ACCESS_TOKEN_SECRET_KEY)
    except SecretNotFoundError:
        # has_secret() and get_secret() both hit the same row; a secret
        # revoked in the gap between the two calls is exactly as valid an
        # outcome as "never configured" - not an error the caller should see.
        return None
    return HomeAssistantAdapter(base_url=base_url, access_token=access_token, timeout_seconds=timeout_seconds)


def build_translating_home_assistant_adapter(
    secret_store: SecretStore, *, integration_id: str, base_url: str, timeout_seconds: float = 10.0
) -> TranslatingHomeAssistantAdapter | None:
    """The `DeviceService`-ready form (S1V2-02-019's error/type
    translation boundary) - for whichever future task actually swaps
    `app/main.py`'s `SimulationDeviceAdapter` wiring for this, the same
    deliberately-deferred step `docs/architecture/mqtt-eventbus.md` and
    `docs/architecture/ha-event-sync.md` already document for
    `MqttEventBus`/`HomeAssistantEventIngestionService`."""
    adapter = build_home_assistant_adapter(
        secret_store, integration_id=integration_id, base_url=base_url, timeout_seconds=timeout_seconds
    )
    if adapter is None:
        return None
    return TranslatingHomeAssistantAdapter(adapter)
