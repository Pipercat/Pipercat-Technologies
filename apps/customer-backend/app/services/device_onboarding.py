"""Unified, manufacturer-independent device onboarding wizard
(S1V2-02-031): discovery → compatibility check → room/name → (test
action reuses the existing device-command path, see below).

"Einheitlicher Wizard unabhängig vom Hersteller": starting a pairing
session is genuinely integration-specific (Zigbee needs a permit-join
duration, Matter needs a pairing code or network PIN, Hue needs a
physical bridge link-button press flow HA exposes only through its
generic config_flow machinery, not a simple service call like ZHA/Matter
- see docs/architecture/device-onboarding-wizard.md's "Bekannte Grenzen"
for why Hue's own pairing service does not exist yet). What genuinely
*is* uniform across every already-built pairing integration
(`ZigbeePairingService`, S1V2-02-022; `MatterCommissioningService`,
S1V2-02-023) is everything *after* pairing starts:
`discover_new_devices(known_before: set[str]) -> list[DomainDevice]` is
the identical method name and signature on both - `DevicePairingPort`
below is that already-existing shared shape, not a new abstraction
invented for this task.

"SystemONE-Profil prüfen ... Beta/unsupported klar kennzeichnen":
`evaluate_compatibility()` is a thin, explicit wrapper around
`app.device_compatibility.lookup_compatibility()` (S1V2-02-026) - `None`
means "no profile registered", which the wizard must surface as
unclassified/Beta, never guess at a status.

"Testaktion anbieten": deliberately no new code here - once a device is
registered and assigned a room/name, "try it" is exactly
`DeviceCommandService.send_command()` (S1V2-02-019), already built,
already permission/PIN-gated, already audited. Duplicating that logic
for onboarding specifically would be the premature-abstraction mistake
this codebase's own conventions avoid.
"""

from typing import Protocol

from app.device_compatibility import DeviceCompatibilityProfile, lookup_compatibility
from app.domain.device import DomainDevice


class DevicePairingPort(Protocol):
    async def discover_new_devices(self, *, known_before: set[str]) -> list[DomainDevice]: ...


class DeviceOnboardingWizardService:
    def evaluate_compatibility(
        self, *, manufacturer: str, model: str, integration_type: str
    ) -> DeviceCompatibilityProfile | None:
        """`None` means no registered profile - the wizard UI must treat
        that the same as an explicit Beta warning, never as "assume
        Certified/Compatible"."""
        return lookup_compatibility(manufacturer, model, integration_type)

    async def discover_devices(self, pairing_service: DevicePairingPort, *, known_before: set[str]) -> list[DomainDevice]:
        """The one step every integration's wizard screen runs through
        identically, regardless of which `pairing_service` started the
        session - proof that the wizard is genuinely manufacturer-
        independent from this point onward."""
        return await pairing_service.discover_new_devices(known_before=known_before)
