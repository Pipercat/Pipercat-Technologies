"""Repository-layer DTOs (S1V2-02-003).

Deliberately separate from app/domain/device.py::DomainDevice: these
represent a *persisted registration row*, not a live adapter-reported
device state. Keeps the service/repository layer decoupled from both
SQLAlchemy models and the domain/adapter layer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoomRecord:
    id: str
    household_id: str
    name: str


@dataclass(frozen=True)
class DeviceRecord:
    id: str
    household_id: str
    integration_id: str
    external_id: str
    name: str
    device_type: str
