"""Low-level Home Assistant REST + WebSocket protocol client (S1V2-02-016).

Encapsulates everything HA-specific: base URL, long-lived access token
auth, the REST `/api/states` and `/api/services/<domain>/<service>`
endpoints, and the WebSocket `/api/websocket` protocol (auth handshake,
command/result correlation by id, event subscription) - including
reconnect-with-backoff for the WebSocket connection. Nothing above this
module (`adapter.py`, `mapping.py`) ever talks HTTP/WebSocket directly.

DEC-118-adjacent: the access token is only ever held in memory here and
sent as an Authorization header - never logged (see `_redacted_headers`
used nowhere except deliberately never passing headers to a logger).
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from .errors import HomeAssistantAuthError, HomeAssistantConnectionError, TransientDeviceError

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RECONNECT_BACKOFF_SECONDS = 2.0
MAX_RECONNECT_BACKOFF_SECONDS = 30.0


def _ws_url(base_url: str) -> str:
    return base_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/api/websocket"


class HomeAssistantClient:
    def __init__(self, base_url: str, access_token: str, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._timeout_seconds = timeout_seconds
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=timeout_seconds,
        )
        self._ws_id_counter = itertools.count(1)

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- REST -----------------------------------------------------------

    async def get_states(self) -> list[dict[str, Any]]:
        try:
            response = await self._http.get("/api/states")
        except httpx.TimeoutException as exc:
            raise TransientDeviceError("Timed out fetching Home Assistant states") from exc
        except httpx.ConnectError as exc:
            raise HomeAssistantConnectionError(f"Could not reach Home Assistant at {self._base_url}") from exc

        self._raise_for_auth(response)
        response.raise_for_status()
        return response.json()

    async def call_service(self, domain: str, service: str, service_data: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            response = await self._http.post(f"/api/services/{domain}/{service}", json=service_data)
        except httpx.TimeoutException as exc:
            raise TransientDeviceError(f"Timed out calling {domain}.{service}") from exc
        except httpx.ConnectError as exc:
            raise HomeAssistantConnectionError(f"Could not reach Home Assistant at {self._base_url}") from exc

        self._raise_for_auth(response)
        response.raise_for_status()
        return response.json()

    def _raise_for_auth(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise HomeAssistantAuthError("Home Assistant rejected the configured access token")

    # --- WebSocket --------------------------------------------------------

    async def _connect_and_authenticate(self) -> Any:
        try:
            ws = await asyncio.wait_for(websockets.connect(_ws_url(self._base_url)), timeout=self._timeout_seconds)
        except (OSError, TimeoutError, asyncio.TimeoutError) as exc:
            raise HomeAssistantConnectionError(f"Could not open a WebSocket connection to {self._base_url}") from exc

        greeting = json.loads(await ws.recv())
        if greeting.get("type") != "auth_required":
            await ws.close()
            raise HomeAssistantConnectionError(f"Unexpected WebSocket greeting: {greeting}")

        await ws.send(json.dumps({"type": "auth", "access_token": self._access_token}))
        auth_result = json.loads(await ws.recv())
        if auth_result.get("type") != "auth_ok":
            await ws.close()
            raise HomeAssistantAuthError("Home Assistant rejected the configured access token over WebSocket")

        return ws

    async def send_command(self, command_type: str, **extra: Any) -> Any:
        """One-shot request/response over a fresh, short-lived WebSocket
        connection - used for infrequent calls like listing the area
        registry, where holding a long-lived connection open isn't worth
        the complexity `subscribe_events` needs for reconnect."""
        command_id = next(self._ws_id_counter)
        ws = await self._connect_and_authenticate()
        try:
            await ws.send(json.dumps({"id": command_id, "type": command_type, **extra}))
            result = json.loads(await ws.recv())
        finally:
            await ws.close()

        if not result.get("success", False):
            raise TransientDeviceError(f"Home Assistant command '{command_type}' failed: {result.get('error')}")
        return result.get("result")

    async def subscribe_events(self, event_type: str = "state_changed") -> AsyncIterator[dict[str, Any]]:
        """Yields Home Assistant events forever, transparently reconnecting
        (with capped exponential backoff) on any connection drop - callers
        never see a raised exception for a transient disconnect, only a
        brief gap in the stream, matching "Reconnect... sauber kapseln"."""
        backoff = DEFAULT_RECONNECT_BACKOFF_SECONDS
        while True:
            try:
                ws = await self._connect_and_authenticate()
            except (HomeAssistantConnectionError, HomeAssistantAuthError):
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_RECONNECT_BACKOFF_SECONDS)
                continue

            subscribe_id = next(self._ws_id_counter)
            try:
                await ws.send(json.dumps({"id": subscribe_id, "type": "subscribe_events", "event_type": event_type}))
                ack = json.loads(await ws.recv())
                if not ack.get("success", False):
                    raise TransientDeviceError(f"Failed to subscribe to '{event_type}': {ack.get('error')}")

                backoff = DEFAULT_RECONNECT_BACKOFF_SECONDS  # reset after a successful (re)subscription
                async for raw_message in ws:
                    message = json.loads(raw_message)
                    if message.get("type") == "event":
                        yield message["event"]
            except (ConnectionClosed, OSError):
                continue  # reconnect loop above handles backoff
            finally:
                await ws.close()
