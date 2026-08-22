"""SystemONE's own device model (S1V2-02-002, `compatibility` added in
S1V2-02-018/-019).

Deliberately independent of any persistence or adapter concerns:
- No SQLAlchemy imports here (the app/db/models.py `Device` row is a
  separate, persistence-shaped concern wired up in S1V2-02-003).
- No Home Assistant concepts (entity_id, domain, service calls).

`manufacturer_metadata` is the *only* place vendor-specific detail may
appear, and it is opaque to domain logic (S1V2-02-002: "Herstellerdetails
nur Metadaten").
"""

from typing import Literal

from pydantic import BaseModel, Field

from .capabilities import CapabilityState, CapabilityType


class DomainDevice(BaseModel):
    id: str
    name: str
    room_id: str | None = None
    device_type: str
    # "supported" unless an adapter explicitly marks an entity type it
    # doesn't understand as "unsupported" (S1V2-02-018:
    # services/home_assistant_adapter/mapping.py). Defaults to
    # "supported" so SimulationDeviceAdapter's seeded devices - which
    # predate this field - need no changes.
    compatibility: Literal["supported", "unsupported"] = "supported"
    manufacturer_metadata: dict = Field(default_factory=dict)
    capabilities: dict[CapabilityType, CapabilityState] = Field(default_factory=dict)
