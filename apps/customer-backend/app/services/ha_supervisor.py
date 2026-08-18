"""Starts, stops, and health-checks Home Assistant as a SystemONE-managed
internal service (S1V2-02-021).

"Endnutzer erhalten keine reguläre HA-Oberfläche, Tokens oder direkte
Konfigurationswege": this module is the *only* place in the codebase that
starts or stops the Home Assistant container - no customer-facing API
route does so, and the container itself has no host-published port
(`infrastructure/docker-compose/docker-compose.yml`) for a customer to
reach directly even if they wanted to. Diagnostic detail
(`export_diagnostics()`) is a plain data structure for internal/support
tooling to render - it is deliberately not wired to any customer-facing
API route, the same precedent `app/diagnostics.py` (S1V2-02-013) already
established for integration diagnostics in general.

Container control goes through the `docker compose` CLI (matching how
this repo already verifies compose configuration - see
`scripts/check-import-boundaries.py`'s sibling gates and
`ha_conftest.py`'s own `docker run` precedent - CI) rather than a Docker
SDK dependency, and is injected as a narrow `ContainerCommandRunner`
Protocol so tests never need a real Docker daemon.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from home_assistant_adapter import HomeAssistantAdapter
from home_assistant_adapter.errors import HomeAssistantAuthError, HomeAssistantConnectionError, TransientDeviceError

logger = logging.getLogger("systemone.customer_backend.ha_supervisor")


class HomeAssistantContainerError(RuntimeError):
    """A `docker compose` start/stop invocation itself failed (non-zero
    exit) - distinct from the container running but Home Assistant inside
    it being unreachable/unhealthy, which `health_check()` reports as a
    status rather than raising."""


class ContainerStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"  # docker compose itself failed to answer - not the same as "stopped"


class HomeAssistantHealthStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"  # no access token stored yet - an ordinary, expected pre-onboarding state
    HEALTHY = "healthy"
    UNREACHABLE = "unreachable"  # container/network problem
    AUTH_REJECTED = "auth_rejected"  # reachable, but the stored token no longer works


class ContainerCommandRunner(Protocol):
    async def __call__(self, *args: str) -> tuple[int, str, str]:
        """Runs `docker compose <args>` and returns (exit_code, stdout, stderr)."""
        ...


async def run_docker_compose_command(*args: str, compose_file: Path) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "docker",
        "compose",
        "-f",
        str(compose_file),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, stdout.decode("utf-8"), stderr.decode("utf-8")


class HomeAssistantSupervisor:
    def __init__(
        self,
        *,
        service_name: str = "home-assistant",
        runner: ContainerCommandRunner,
        adapter_factory: Callable[[], Awaitable[HomeAssistantAdapter | None]],
    ) -> None:
        self._service_name = service_name
        self._runner = runner
        self._adapter_factory = adapter_factory

    async def start(self) -> None:
        exit_code, _stdout, stderr = await self._runner("up", "-d", self._service_name)
        if exit_code != 0:
            raise HomeAssistantContainerError(f"Failed to start the Home Assistant container: {stderr.strip()}")
        logger.info("ha_container_started")

    async def stop(self) -> None:
        exit_code, _stdout, stderr = await self._runner("stop", self._service_name)
        if exit_code != 0:
            raise HomeAssistantContainerError(f"Failed to stop the Home Assistant container: {stderr.strip()}")
        logger.info("ha_container_stopped")

    async def container_status(self) -> ContainerStatus:
        exit_code, stdout, _stderr = await self._runner(
            "ps", "--status", "running", "--format", "{{.Name}}", self._service_name
        )
        if exit_code != 0:
            return ContainerStatus.UNKNOWN
        return ContainerStatus.RUNNING if stdout.strip() else ContainerStatus.STOPPED

    async def health_check(self) -> HomeAssistantHealthStatus:
        """Container-running is necessary but not sufficient - Home
        Assistant can still be mid-startup, unreachable over the network,
        or rejecting the stored token, all distinct from "not onboarded
        at all". `adapter_factory` (see `app.services.ha_provisioning`)
        already returns `None` for "not onboarded", so that case never
        even attempts a network call."""
        adapter = await self._adapter_factory()
        if adapter is None:
            return HomeAssistantHealthStatus.NOT_CONFIGURED
        try:
            await adapter.list_devices()
        except HomeAssistantAuthError:
            return HomeAssistantHealthStatus.AUTH_REJECTED
        except (HomeAssistantConnectionError, TransientDeviceError):
            return HomeAssistantHealthStatus.UNREACHABLE
        return HomeAssistantHealthStatus.HEALTHY

    async def export_diagnostics(self) -> dict:
        """Internal/support-facing technical detail (S1V2-02-021:
        "Diagnose darf technische HA-Details intern anzeigen") - never a
        customer-facing response shape, and never includes the access
        token itself (only whether Home Assistant is reachable with it)."""
        container_status = await self.container_status()
        health = await self.health_check()
        return {"containerStatus": container_status.value, "health": health.value}
