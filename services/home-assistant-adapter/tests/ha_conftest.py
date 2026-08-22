"""Real-Home-Assistant test fixture (S1V2-02-016 DoD: "... echter
HA-Integrationstest"). Not named conftest.py on purpose - importing it
is opt-in (only test_real_ha_integration.py needs it), mirroring
apps/customer-backend/tests/db_conftest.py's pattern for real-Postgres
tests.

Talks to a Home Assistant instance already running with the `demo:`
platform enabled (see docs/architecture/home-assistant-adapter.md for
how to start one locally, or the `home-assistant-adapter` CI job for
how it's started in CI) and drives its onboarding REST flow
programmatically to create the first admin user and get an access
token - HA has no non-interactive "just give me a token" bootstrap path,
so this reproduces what a human would do through the web UI once, via
the same REST endpoints the UI itself calls.

Assumes a *freshly started, never-onboarded* instance (the "user"
onboarding step not yet done) - CI always starts one fresh per run; for
local reruns, remove the container's config volume (or start a new
container) between runs rather than reusing an already-onboarded one.
"""

import os

import httpx
import pytest

requires_home_assistant = pytest.mark.skipif(
    "HOME_ASSISTANT_URL" not in os.environ,
    reason="HOME_ASSISTANT_URL not set - real Home Assistant integration tests need a running instance "
    "(see docs/architecture/home-assistant-adapter.md for how to start one locally with Docker).",
)


async def onboard_and_get_long_lived_token(base_url: str) -> str:
    client_id = base_url.rstrip("/") + "/"

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        status = (await client.get("/api/onboarding")).json()
        steps_done = {step["step"]: step["done"] for step in status}

        if steps_done.get("user", False):
            raise RuntimeError(
                "This Home Assistant instance is already onboarded - ha_conftest.py only supports a "
                "freshly started instance. Start a new container (or clear its config volume) and retry."
            )

        response = await client.post(
            "/api/onboarding/users",
            json={
                "client_id": client_id,
                "name": "SystemONE Test Admin",
                "username": "systemone-test",
                "password": "systemone-test-password-not-for-real-use",
                "language": "en",
            },
        )
        response.raise_for_status()
        auth_code = response.json()["auth_code"]

        token_response = await client.post(
            "/auth/token",
            data={"grant_type": "authorization_code", "code": auth_code, "client_id": client_id},
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        auth_headers = {"Authorization": f"Bearer {access_token}"}

        if not steps_done.get("core_config", False):
            response = await client.post("/api/onboarding/core_config", headers=auth_headers)
            response.raise_for_status()

        if not steps_done.get("analytics", False):
            response = await client.post("/api/onboarding/analytics", headers=auth_headers)
            if response.status_code not in (200, 404):  # 404: step removed in some HA versions
                response.raise_for_status()

        # Home Assistant only exposes long-lived-token creation over the
        # WebSocket API, not REST. The OAuth access_token from /auth/token
        # above (~30 minute lifetime) is already enough for a single test
        # run, so the adapter's own WebSocket client is not needed just to
        # mint a token here.
        return access_token


@pytest.fixture(scope="session")
def home_assistant_base_url() -> str:
    return os.environ["HOME_ASSISTANT_URL"]


@pytest.fixture(scope="session")
async def home_assistant_access_token(home_assistant_base_url: str) -> str:
    return await onboard_and_get_long_lived_token(home_assistant_base_url)
