"""Interface boundary for the mandatory Home Assistant backbone (ADR-0002).

This module intentionally defines only the public contract. The real
connection to a Home Assistant instance (REST/WebSocket API, auth, entity
sync) is implemented in S1V2-02-016 ff. Keeping the interface separate lets
apps/customer-backend depend on a stable contract before that work lands.

Mirrors the abstract-adapter pattern already proven in the existing
Node.js pilot (mvp/systemone-pi/lib/adapter.js) — discover/pair/list/apply,
translated to the Home-Assistant-mediated model.
"""

from abc import ABC, abstractmethod
from typing import Any


class HomeAssistantAdapter(ABC):
    """Single production integration boundary between SystemONE's Domain/
    Device Model and Home Assistant. No other code path may talk to Home
    Assistant, Zigbee, Matter, Shelly or Hue directly (see ADR-0002,
    "Architekturgrenzen")."""

    @abstractmethod
    async def import_devices(self) -> list[dict[str, Any]]:
        """Import Home Assistant devices/entities/areas for stable mapping
        onto SystemONE devices (S1V2-02-017)."""
        raise NotImplementedError

    @abstractmethod
    async def apply_capability(self, device_id: str, capability: str, value: Any) -> None:
        """Execute a normalized SystemONE device command via Home Assistant
        (S1V2-02-019)."""
        raise NotImplementedError

    @abstractmethod
    async def subscribe_state_events(self) -> Any:
        """Stream live Home Assistant state changes back into SystemONE's
        normalized event model (S1V2-02-020)."""
        raise NotImplementedError
