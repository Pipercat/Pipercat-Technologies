"""The port the domain layer depends on (S1V2-02-002).

Deliberately `typing.Protocol` (structural typing), not an ABC base class:
`services/home-assistant-adapter`'s `HomeAssistantAdapter` can satisfy this
port purely by matching its method shapes, without importing
`apps/customer-backend` at all - avoiding a reverse dependency that would
violate the import boundaries in docs/architecture/repo-structure.md
(home-assistant-adapter must not import from any app). This is the
standard hexagonal-architecture "port" pattern: adapters implement it,
the domain only depends on the shape.
"""

from typing import Protocol

from .capabilities import CapabilityCommand, CapabilityState
from .device import DomainDevice


class DeviceAdapterPort(Protocol):
    async def list_devices(self) -> list[DomainDevice]: ...

    async def apply_command(self, device_id: str, command: CapabilityCommand) -> CapabilityState:
        """Executes a command and returns the resulting state. Raises
        DeviceNotFoundError / CapabilityNotSupportedError as appropriate
        (see errors.py) - never silently no-ops."""
        ...
