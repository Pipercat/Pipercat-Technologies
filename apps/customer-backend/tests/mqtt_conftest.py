"""Real (not mocked) local Mosquitto broker management for the S1V2-02-004
integration tests. Opt-in import, like tests/db_conftest.py, so the rest of
the suite doesn't need mosquitto installed.
"""

import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

MOSQUITTO_CANDIDATES = [
    "/opt/homebrew/opt/mosquitto/sbin/mosquitto",  # macOS Homebrew (Apple Silicon)
    "/usr/local/opt/mosquitto/sbin/mosquitto",  # macOS Homebrew (Intel)
    "mosquitto",  # Linux (apt/CI), resolved via PATH
]


def _find_mosquitto() -> str | None:
    for candidate in MOSQUITTO_CANDIDATES:
        if candidate == "mosquitto":
            found = shutil.which("mosquitto")
            if found:
                return found
        elif Path(candidate).exists():
            return candidate
    return None


MOSQUITTO_BIN = _find_mosquitto()

requires_mosquitto = pytest.mark.skipif(
    MOSQUITTO_BIN is None,
    reason="mosquitto broker not found - install via `brew install mosquitto` or `apt-get install mosquitto`",
)


class TestBroker:
    """Controls a single local Mosquitto process the test can stop/start on
    demand, to exercise reconnect/duplicate-delivery/offline behaviour
    against a real broker instead of a mock."""

    def __init__(self, port: int) -> None:
        self.port = port
        self._process: subprocess.Popen | None = None
        self._config_dir = tempfile.mkdtemp(prefix="systemone-mqtt-test-")
        self._config_path = Path(self._config_dir) / "mosquitto.conf"
        self._config_path.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")

    def start(self) -> None:
        assert MOSQUITTO_BIN is not None
        self._process = subprocess.Popen(
            [MOSQUITTO_BIN, "-c", str(self._config_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_until_accepting_connections()

    def stop(self) -> None:
        if self._process is not None:
            self._process.kill()
            self._process.wait(timeout=5)
            self._process = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def _wait_until_accepting_connections(self, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"mosquitto did not start accepting connections on port {self.port} in time")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def test_broker():
    broker = TestBroker(port=_free_port())
    broker.start()
    try:
        yield broker
    finally:
        broker.stop()
