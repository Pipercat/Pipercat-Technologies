"""S1V2-02-029 Definition of Done: "Neuinstallation kann per LAN
vollständig eingerichtet werden; WLAN-Fallback getestet; kein
dauerhafter offener Setup-Hotspot."

Uses a fake `nmcli` command runner - no real NetworkManager/D-Bus/Wi-Fi
hardware needed for any test here (none of which exists in this
sandbox). See docs/architecture/network-setup.md's "Bekannte Grenzen"
for what still needs a real Linux host with NetworkManager to verify.
"""

import asyncio
import stat

import pytest

from app.services.network_setup import ConnectivityKind, NetworkSetupError, NetworkSetupService


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = {}
        self.default_response: tuple[int, str, str] = (0, "", "")

    def set_device_status(self, pairs: list[tuple[str, str]]) -> None:
        stdout = "\n".join(f"{kind}:{state}" for kind, state in pairs) + "\n"
        self.responses[("-t", "-f", "TYPE,STATE", "device", "status")] = (0, stdout, "")

    def set_response(self, args: tuple[str, ...], *, exit_code: int, stdout: str = "", stderr: str = "") -> None:
        self.responses[args] = (exit_code, stdout, stderr)

    def set_default_response(self, *, exit_code: int, stdout: str = "", stderr: str = "") -> None:
        """For calls whose exact args aren't known in advance (e.g. a
        dynamically-generated connection-profile id)."""
        self.default_response = (exit_code, stdout, stderr)

    async def __call__(self, *args: str) -> tuple[int, str, str]:
        self.calls.append(args)
        return self.responses.get(args, self.default_response)


def _service(runner: _FakeRunner, tmp_path, **overrides) -> NetworkSetupService:
    defaults = {
        "runner": runner,
        "connection_profile_dir": tmp_path,
        "hotspot_ssid": "SystemONE-Setup",
        "hotspot_password": "setup-hotspot-password",
        "hotspot_timeout_seconds": 900,
    }
    defaults.update(overrides)
    return NetworkSetupService(**defaults)


# --- connectivity detection: Ethernet first ---------------------------------


async def test_ethernet_connected_true_when_a_wired_device_is_connected(tmp_path):
    runner = _FakeRunner()
    runner.set_device_status([("ethernet", "connected")])
    service = _service(runner, tmp_path)

    assert await service.ethernet_connected() is True


async def test_ethernet_connected_false_when_only_wifi_is_connected(tmp_path):
    runner = _FakeRunner()
    runner.set_device_status([("ethernet", "disconnected"), ("wifi", "connected")])
    service = _service(runner, tmp_path)

    assert await service.ethernet_connected() is False


async def test_current_connectivity_prefers_ethernet_over_wifi(tmp_path):
    """Even if both happen to be connected, Ethernet is reported -
    "Ethernet ist bevorzugter Standard"."""
    runner = _FakeRunner()
    runner.set_device_status([("ethernet", "connected"), ("wifi", "connected")])
    service = _service(runner, tmp_path)

    assert await service.current_connectivity() == ConnectivityKind.ETHERNET


async def test_current_connectivity_is_none_with_nothing_connected(tmp_path):
    runner = _FakeRunner()
    runner.set_device_status([("ethernet", "disconnected"), ("wifi", "disconnected")])
    service = _service(runner, tmp_path)

    assert await service.current_connectivity() == ConnectivityKind.NONE


async def test_current_connectivity_handles_a_failed_nmcli_call_as_none(tmp_path):
    runner = _FakeRunner()
    runner.set_response(("-t", "-f", "TYPE,STATE", "device", "status"), exit_code=1, stderr="nmcli not available")
    service = _service(runner, tmp_path)

    assert await service.current_connectivity() == ConnectivityKind.NONE


# --- "Temporärer Setup-Hotspot nur wenn technisch nötig" --------------------


async def test_hotspot_not_needed_when_ethernet_is_connected(tmp_path):
    runner = _FakeRunner()
    runner.set_device_status([("ethernet", "connected")])
    service = _service(runner, tmp_path)

    assert await service.should_start_setup_hotspot() is False


async def test_hotspot_not_needed_when_wifi_is_already_connected(tmp_path):
    runner = _FakeRunner()
    runner.set_device_status([("ethernet", "disconnected"), ("wifi", "connected")])
    service = _service(runner, tmp_path)

    assert await service.should_start_setup_hotspot() is False


async def test_hotspot_needed_when_nothing_is_connected(tmp_path):
    runner = _FakeRunner()
    runner.set_device_status([("ethernet", "disconnected"), ("wifi", "disconnected")])
    service = _service(runner, tmp_path)

    assert await service.should_start_setup_hotspot() is True


# --- WLAN-Fallback: connect_wifi() -------------------------------------------


async def test_connect_wifi_writes_a_restrictively_permissioned_profile(tmp_path):
    runner = _FakeRunner()
    service = _service(runner, tmp_path)

    await service.connect_wifi(ssid="MyHomeNetwork", password="hunter2-passphrase")

    profiles = list(tmp_path.glob("systemone-wifi-*.nmconnection"))
    assert len(profiles) == 1
    content = profiles[0].read_text()
    assert "ssid=MyHomeNetwork" in content
    assert "psk=hunter2-passphrase" in content
    assert "mode=infrastructure" in content
    mode = stat.S_IMODE(profiles[0].stat().st_mode)
    assert mode == 0o600


async def test_connect_wifi_never_passes_the_password_as_a_command_argument(tmp_path):
    """"WLAN-Secrets sicher behandeln": the password must never be an
    argv value an unrelated local process could read via `ps aux`."""
    runner = _FakeRunner()
    service = _service(runner, tmp_path)

    await service.connect_wifi(ssid="MyHomeNetwork", password="hunter2-passphrase")

    for call in runner.calls:
        assert "hunter2-passphrase" not in call


async def test_connect_wifi_activates_the_written_profile(tmp_path):
    runner = _FakeRunner()
    service = _service(runner, tmp_path)

    await service.connect_wifi(ssid="MyHomeNetwork", password="hunter2-passphrase")

    assert len(runner.calls) == 1
    assert runner.calls[0][:2] == ("connection", "up")


async def test_connect_wifi_returns_false_on_a_failed_activation(tmp_path):
    runner = _FakeRunner()
    runner.set_default_response(exit_code=1, stderr="no network with that SSID found")
    service = _service(runner, tmp_path)

    result = await service.connect_wifi(ssid="NonexistentNetwork", password="irrelevant")

    assert result is False


# --- Setup-Hotspot: nötig, zeitlich begrenzt, abschaltbar -------------------


async def test_start_setup_hotspot_never_passes_the_password_as_a_command_argument(tmp_path):
    runner = _FakeRunner()
    service = _service(runner, tmp_path, hotspot_password="setup-hotspot-secret")

    await service.start_setup_hotspot()

    for call in runner.calls:
        assert "setup-hotspot-secret" not in call
    await service.stop_setup_hotspot()


async def test_start_setup_hotspot_writes_an_ap_mode_shared_profile(tmp_path):
    runner = _FakeRunner()
    service = _service(runner, tmp_path)

    await service.start_setup_hotspot()

    profile = tmp_path / "systemone-setup-hotspot.nmconnection"
    content = profile.read_text()
    assert "mode=ap" in content
    assert "method=shared" in content
    assert "ssid=SystemONE-Setup" in content
    await service.stop_setup_hotspot()


async def test_start_setup_hotspot_raises_on_failure(tmp_path):
    runner = _FakeRunner()
    runner.set_response(("connection", "up", "systemone-setup-hotspot"), exit_code=1, stderr="no Wi-Fi device available")
    service = _service(runner, tmp_path)

    with pytest.raises(NetworkSetupError):
        await service.start_setup_hotspot()


async def test_stop_setup_hotspot_brings_the_connection_down(tmp_path):
    runner = _FakeRunner()
    service = _service(runner, tmp_path)
    await service.start_setup_hotspot()

    await service.stop_setup_hotspot()

    assert ("connection", "down", "systemone-setup-hotspot") in runner.calls


async def test_hotspot_auto_stops_after_its_timeout(tmp_path):
    """"Zeitlich begrenzt": a safety net independent of any explicit stop."""
    runner = _FakeRunner()
    service = _service(runner, tmp_path, hotspot_timeout_seconds=0.01)

    await service.start_setup_hotspot()
    await asyncio.sleep(0.05)

    assert ("connection", "down", "systemone-setup-hotspot") in runner.calls


async def test_explicit_stop_cancels_the_pending_auto_stop_timeout(tmp_path):
    """No dangling task fires a redundant/late stop after an explicit one."""
    runner = _FakeRunner()
    service = _service(runner, tmp_path, hotspot_timeout_seconds=0.02)

    await service.start_setup_hotspot()
    await service.stop_setup_hotspot()
    runner.calls.clear()
    await asyncio.sleep(0.05)

    assert ("connection", "down", "systemone-setup-hotspot") not in runner.calls
