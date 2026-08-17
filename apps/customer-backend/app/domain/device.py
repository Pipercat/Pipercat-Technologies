"""SystemONE's own device model (S1V2-02-002).

Deliberately independent of any persistence or adapter concerns:
- No SQLAlchemy imports here (the app/db/models.py `Device` row is a
  separate, persistence-shaped concern wired up in S1V2-02-003).
- No Home Assistant concepts (entity_id, domain, service calls).

`manufacturer_metadata` is the *only* place vendor-specific detail may
appear, and it is opaque to domain logic (S1V2-02-002: "Herstellerdetails
nur Metadaten").
"""

from pydantic import BaseModel, Field

from .capabilities import CapabilityState, CapabilityType


class DomainDevice(BaseModel):
    id: str
    name: str
    room_id: str | None = None
    device_type: str
    manufacturer_metadata: dict = Field(default_factory=dict)
    capabilities: dict[CapabilityType, CapabilityState] = Field(default_factory=dict)
