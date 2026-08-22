"""Ethernet-first, WLAN-fallback network setup (S1V2-02-029).

"Ethernet ist bevorzugter Standard, WLAN Fallback": `should_start_setup_hotspot()`
only ever returns `True` when neither a wired connection nor an already-
connected Wi-Fi exists - the temporary setup hotspot is a last resort,
never the default path.

"Setup darf ohne Internet funktionieren": every operation here is local
NetworkManager configuration (via `nmcli`/D-Bus) - nothing in this module
makes an outbound network call at all, so it works identically whether
or not the resulting connection actually reaches the internet.

"WLAN-Secrets sicher behandeln": `connect_wifi()`/`start_setup_hotspot()`
both write a NetworkManager keyfile connection profile
(https://networkmanager.dev/docs/api/latest/nm-settings-keyfile.html,
format cross-checked against NetworkManager's own test fixture
`src/core/settings/plugins/keyfile/tests/keyfiles/
Test_New_Wireless_Group_Names`) with `0600` permissions, rather than
passing the password as an `nmcli ... password <password>` CLI argument -
an argv-visible secret would sit in this host's process list (`ps aux`)
for any other local process to read. `nmcli connection up <profile-id>`
then activates the already-written, already-secured profile.

"Temporärer Setup-Hotspot nur wenn technisch nötig, zeitlich begrenzt und
nach Abschluss deaktiviert": `should_start_setup_hotspot()` gates
"nötig"; `start_setup_hotspot()` always schedules an automatic
`stop_setup_hotspot()` after `hotspot_timeout_seconds` as a safety net
("zeitlich begrenzt"); the pairing/setup flow is expected to call
`stop_setup_hotspot()` explicitly once setup genuinely completes
("nach Abschluss deaktiviert"), which also cancels the pending timeout.

Command syntax verified against NetworkManager's own `nmcli` source
(`src/nmcli/devices.c`) rather than guessed - `nmcli device wifi hotspot
[ifname ...] [con-name ...] [ssid ...] [password ...]` and `nmcli device
wifi connect <SSID> [password ...] [ifname ...] [name ...]` are real,
current subcommands; stopping a hotspot via `nmcli connection down
<name>` is the tool's own documented way to do it.

This module only ever talks to the *local* NetworkManager via `nmcli` -
it needs host-level D-Bus/NetworkManager access that a plain Docker
container does not have by default; see
docs/architecture/network-setup.md for the docker-compose.yml volume
mounts (`/var/run/dbus`, `/etc/NetworkManager/system-connections`) this
depends on, and for what could not be verified without a real Linux host
with NetworkManager and real network hardware.
"""

import asyncio
import uuid
from enum import Enum
from pathlib import Path
from typing import Protocol


class NetworkSetupError(RuntimeError):
    """A `nmcli` invocation that was expected to succeed did not."""


class ConnectivityKind(str, Enum):
    ETHERNET = "ethernet"
    WIFI = "wifi"
    NONE = "none"


class NetworkCommandRunner(Protocol):
    async def __call__(self, *args: str) -> tuple[int, str, str]:
        """Runs `nmcli <args>` and returns (exit_code, stdout, stderr)."""
        ...


async def run_nmcli_command(*args: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "nmcli", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, stdout.decode("utf-8"), stderr.decode("utf-8")


def _render_wifi_connection_profile(*, connection_id: str, ssid: str, password: str, mode: str, ipv4_method: str) -> str:
    return (
        "[connection]\n"
        f"id={connection_id}\n"
        f"uuid={uuid.uuid4()}\n"
        "type=wifi\n"
        "\n"
        "[wifi]\n"
        f"ssid={ssid}\n"
        f"mode={mode}\n"
        "\n"
        "[wifi-security]\n"
        "key-mgmt=wpa-psk\n"
        f"psk={password}\n"
        "\n"
        "[ipv4]\n"
        f"method={ipv4_method}\n"
    )


class NetworkSetupService:
    def __init__(
        self,
        *,
        runner: NetworkCommandRunner,
        connection_profile_dir: Path,
        hotspot_ssid: str,
        hotspot_password: str,
        hotspot_con_name: str = "systemone-setup-hotspot",
        hotspot_ifname: str = "wlan0",
        hotspot_timeout_seconds: int = 900,
    ) -> None:
        self._runner = runner
        self._connection_profile_dir = connection_profile_dir
        self._hotspot_ssid = hotspot_ssid
        self._hotspot_password = hotspot_password
        self._hotspot_con_name = hotspot_con_name
        self._hotspot_ifname = hotspot_ifname
        self._hotspot_timeout_seconds = hotspot_timeout_seconds
        self._hotspot_timeout_task: asyncio.Task | None = None

    async def _device_status(self) -> list[tuple[str, str]]:
        """Returns (type, state) pairs, e.g. [("ethernet", "connected"),
        ("wifi", "disconnected")] - `-t -f TYPE,STATE` is `nmcli`'s own
        machine-parseable terse output mode."""
        exit_code, stdout, _stderr = await self._runner("-t", "-f", "TYPE,STATE", "device", "status")
        if exit_code != 0:
            return []
        pairs = []
        for line in stdout.strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 2:
                pairs.append((parts[0], parts[1]))
        return pairs

    async def ethernet_connected(self) -> bool:
        return any(kind == "ethernet" and state == "connected" for kind, state in await self._device_status())

    async def has_connected_wifi(self) -> bool:
        return any(kind == "wifi" and state == "connected" for kind, state in await self._device_status())

    async def current_connectivity(self) -> ConnectivityKind:
        if await self.ethernet_connected():
            return ConnectivityKind.ETHERNET
        if await self.has_connected_wifi():
            return ConnectivityKind.WIFI
        return ConnectivityKind.NONE

    async def should_start_setup_hotspot(self) -> bool:
        """"Nur wenn technisch nötig" - neither a wired connection nor an
        already-connected Wi-Fi exists."""
        return await self.current_connectivity() == ConnectivityKind.NONE

    async def connect_wifi(self, *, ssid: str, password: str) -> bool:
        connection_id = f"systemone-wifi-{uuid.uuid4().hex[:8]}"
        self._write_profile(connection_id=connection_id, ssid=ssid, password=password, mode="infrastructure", ipv4_method="auto")

        exit_code, _stdout, _stderr = await self._runner("connection", "up", connection_id)
        return exit_code == 0

    async def start_setup_hotspot(self) -> None:
        self._write_profile(
            connection_id=self._hotspot_con_name,
            ssid=self._hotspot_ssid,
            password=self._hotspot_password,
            mode="ap",
            ipv4_method="shared",  # NetworkManager's DHCP-server/NAT mode for hotspots/tethering
        )

        exit_code, _stdout, stderr = await self._runner("connection", "up", self._hotspot_con_name)
        if exit_code != 0:
            raise NetworkSetupError(f"Failed to start the setup hotspot: {stderr.strip()}")

        if self._hotspot_timeout_task is not None:
            self._hotspot_timeout_task.cancel()
        self._hotspot_timeout_task = asyncio.create_task(self._auto_stop_after_timeout())

    async def _auto_stop_after_timeout(self) -> None:
        await asyncio.sleep(self._hotspot_timeout_seconds)
        await self.stop_setup_hotspot()

    async def stop_setup_hotspot(self) -> None:
        if self._hotspot_timeout_task is not None:
            self._hotspot_timeout_task.cancel()
            self._hotspot_timeout_task = None
        await self._runner("connection", "down", self._hotspot_con_name)

    def _write_profile(self, *, connection_id: str, ssid: str, password: str, mode: str, ipv4_method: str) -> None:
        self._connection_profile_dir.mkdir(parents=True, exist_ok=True)
        profile_path = self._connection_profile_dir / f"{connection_id}.nmconnection"
        profile_path.write_text(
            _render_wifi_connection_profile(
                connection_id=connection_id, ssid=ssid, password=password, mode=mode, ipv4_method=ipv4_method
            )
        )
        profile_path.chmod(0o600)
