"""S1V2-02-021 DoD: "Normaler Kunde kann SystemONE komplett nutzen, ohne
zu wissen oder bedienen zu müssen, dass HA darunter läuft" - the
start/stop/health-check half. Uses a fake `docker compose` command runner
and a fake adapter factory, so this file needs neither a real Docker
daemon nor a real Home Assistant instance - `infrastructure/docker-compose/
docker-compose.yml`'s actual container definition is separately validated
by `docker compose config` (see docs/architecture/repo-structure.md's
build/test table)."""

import shutil
from pathlib import Path

import pytest
from home_assistant_adapter.errors import HomeAssistantAuthError, HomeAssistantConnectionError, TransientDeviceError

from app.services.ha_supervisor import (
    ContainerStatus,
    HomeAssistantContainerError,
    HomeAssistantHealthStatus,
    HomeAssistantSupervisor,
    run_docker_compose_command,
)

_COMPOSE_FILE = Path(__file__).parents[3] / "infrastructure" / "docker-compose" / "docker-compose.yml"
requires_docker = pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not available in this environment")


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = {}

    def set_response(self, args: tuple[str, ...], *, exit_code: int, stdout: str = "", stderr: str = "") -> None:
        self.responses[args] = (exit_code, stdout, stderr)

    async def __call__(self, *args: str) -> tuple[int, str, str]:
        self.calls.append(args)
        return self.responses.get(args, (0, "", ""))


class _FakeAdapter:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises

    async def list_devices(self):
        if self._raises is not None:
            raise self._raises
        return []


def _supervisor(runner: _FakeRunner, adapter) -> HomeAssistantSupervisor:
    async def adapter_factory():
        return adapter

    return HomeAssistantSupervisor(runner=runner, adapter_factory=adapter_factory)


# --- start/stop ----------------------------------------------------------


async def test_start_runs_docker_compose_up_for_the_service():
    runner = _FakeRunner()
    supervisor = _supervisor(runner, None)

    await supervisor.start()

    assert runner.calls == [("up", "-d", "home-assistant")]


async def test_start_raises_on_a_failed_compose_invocation():
    runner = _FakeRunner()
    runner.set_response(("up", "-d", "home-assistant"), exit_code=1, stderr="no such image")
    supervisor = _supervisor(runner, None)

    try:
        await supervisor.start()
        raise AssertionError("expected HomeAssistantContainerError")
    except HomeAssistantContainerError as exc:
        assert "no such image" in str(exc)


async def test_stop_runs_docker_compose_stop_for_the_service():
    runner = _FakeRunner()
    supervisor = _supervisor(runner, None)

    await supervisor.stop()

    assert runner.calls == [("stop", "home-assistant")]


async def test_stop_raises_on_a_failed_compose_invocation():
    runner = _FakeRunner()
    runner.set_response(("stop", "home-assistant"), exit_code=1, stderr="container not found")
    supervisor = _supervisor(runner, None)

    try:
        await supervisor.stop()
        raise AssertionError("expected HomeAssistantContainerError")
    except HomeAssistantContainerError as exc:
        assert "container not found" in str(exc)


# --- container status ------------------------------------------------------


async def test_container_status_running_when_ps_reports_the_container():
    runner = _FakeRunner()
    runner.set_response(
        ("ps", "--status", "running", "--format", "{{.Name}}", "home-assistant"),
        exit_code=0,
        stdout="docker-compose-home-assistant-1\n",
    )
    supervisor = _supervisor(runner, None)

    assert await supervisor.container_status() == ContainerStatus.RUNNING


async def test_container_status_stopped_when_ps_reports_nothing():
    runner = _FakeRunner()
    runner.set_response(("ps", "--status", "running", "--format", "{{.Name}}", "home-assistant"), exit_code=0, stdout="")
    supervisor = _supervisor(runner, None)

    assert await supervisor.container_status() == ContainerStatus.STOPPED


async def test_container_status_unknown_when_docker_compose_itself_fails():
    runner = _FakeRunner()
    runner.set_response(
        ("ps", "--status", "running", "--format", "{{.Name}}", "home-assistant"), exit_code=1, stderr="docker daemon down"
    )
    supervisor = _supervisor(runner, None)

    assert await supervisor.container_status() == ContainerStatus.UNKNOWN


# --- health check ------------------------------------------------------------


async def test_health_check_not_configured_when_no_adapter_can_be_built():
    supervisor = _supervisor(_FakeRunner(), None)

    assert await supervisor.health_check() == HomeAssistantHealthStatus.NOT_CONFIGURED


async def test_health_check_healthy_when_list_devices_succeeds():
    supervisor = _supervisor(_FakeRunner(), _FakeAdapter())

    assert await supervisor.health_check() == HomeAssistantHealthStatus.HEALTHY


async def test_health_check_unreachable_on_connection_error():
    supervisor = _supervisor(_FakeRunner(), _FakeAdapter(raises=HomeAssistantConnectionError("down")))

    assert await supervisor.health_check() == HomeAssistantHealthStatus.UNREACHABLE


async def test_health_check_unreachable_on_transient_error():
    supervisor = _supervisor(_FakeRunner(), _FakeAdapter(raises=TransientDeviceError("timeout")))

    assert await supervisor.health_check() == HomeAssistantHealthStatus.UNREACHABLE


async def test_health_check_auth_rejected_on_auth_error():
    supervisor = _supervisor(_FakeRunner(), _FakeAdapter(raises=HomeAssistantAuthError("bad token")))

    assert await supervisor.health_check() == HomeAssistantHealthStatus.AUTH_REJECTED


# --- diagnostics (internal-only technical detail) ---------------------------


async def test_export_diagnostics_combines_container_status_and_health():
    runner = _FakeRunner()
    runner.set_response(
        ("ps", "--status", "running", "--format", "{{.Name}}", "home-assistant"),
        exit_code=0,
        stdout="docker-compose-home-assistant-1\n",
    )
    supervisor = _supervisor(runner, _FakeAdapter())

    diagnostics = await supervisor.export_diagnostics()

    assert diagnostics == {"containerStatus": "running", "health": "healthy"}


# --- real docker compose CLI plumbing ---------------------------------------


@requires_docker
async def test_run_docker_compose_command_invokes_the_real_cli():
    """The only test in this file that shells out for real - `config` is
    side-effect-free (no containers started/stopped), so this safely
    exercises the actual subprocess plumbing `HomeAssistantSupervisor`
    uses in production against the real compose file, complementing the
    fully-faked tests above."""
    exit_code, stdout, _stderr = await run_docker_compose_command("config", "--services", compose_file=_COMPOSE_FILE)

    assert exit_code == 0
    assert "home-assistant" in stdout.split()
