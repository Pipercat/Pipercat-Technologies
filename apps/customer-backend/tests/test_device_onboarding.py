"""S1V2-02-031 Definition of Done: "Mindestens Hue und Zigbee laufen über
denselben SystemONE-Flow" - the Zigbee+Matter half (see
docs/architecture/device-onboarding-wizard.md's "Bekannte Grenzen" for
why Hue's own pairing mechanism does not exist yet: Home Assistant's Hue
integration pairs via a physical bridge link-button press through HA's
generic config_flow machinery, not a simple service/command call like
ZHA/Matter, and is a separate, larger undertaking).

Proves `DeviceOnboardingWizardService.discover_devices()` is genuinely
integration-independent by running the *exact same* wizard method against
a `ZigbeePairingService` (S1V2-02-022) and a `MatterCommissioningService`
(S1V2-02-023) - both already satisfy `DevicePairingPort` structurally,
with no wizard-specific code needed on either.
"""

from app.device_compatibility import (
    DEVICE_COMPATIBILITY_REGISTRY,
    CompatibilityStatus,
    DeviceCompatibilityProfile,
    register_profile,
)
from app.domain.capabilities import CapabilityType, OnOffState
from app.domain.device import DomainDevice
from app.services.device_onboarding import DeviceOnboardingWizardService
from app.services.matter_commissioning import MatterCommissioningService
from app.services.zigbee_pairing import ZigbeePairingService
from tests.fakes import InMemoryAuditRecorder, make_actor


def _light(device_id: str) -> DomainDevice:
    return DomainDevice(
        id=device_id, name="Lamp", device_type="light", capabilities={CapabilityType.ON_OFF: OnOffState(is_on=True)}
    )


class _FakeZigbeeAdapter:
    def __init__(self) -> None:
        self.devices: list[DomainDevice] = []

    async def list_devices(self) -> list[DomainDevice]:
        return list(self.devices)

    async def start_zigbee_pairing(self, *, duration_seconds: int = 60) -> None:
        pass


class _FakeMatterAdapter:
    def __init__(self) -> None:
        self.devices: list[DomainDevice] = []

    async def list_devices(self) -> list[DomainDevice]:
        return list(self.devices)

    async def start_matter_commissioning_with_code(self, *, code: str, network_only: bool = True) -> None:
        pass


# --- "einheitlicher Wizard": derselbe Discovery-Aufruf für beide -----------


async def test_discover_devices_works_uniformly_across_zigbee_and_matter():
    wizard = DeviceOnboardingWizardService()

    zigbee_adapter = _FakeZigbeeAdapter()
    zigbee_service = ZigbeePairingService(zigbee_adapter, InMemoryAuditRecorder())
    zigbee_actor = make_actor("devices:manage")
    known_before = await zigbee_service.start_pairing(zigbee_actor)
    zigbee_adapter.devices.append(_light("zigbee-light-1"))

    matter_adapter = _FakeMatterAdapter()
    matter_service = MatterCommissioningService(matter_adapter, InMemoryAuditRecorder())
    matter_actor = make_actor("devices:manage")
    matter_known_before = await matter_service.start_commissioning_with_code(matter_actor, code="MT:ABCDEF")
    matter_adapter.devices.append(_light("matter-light-1"))

    zigbee_discovered = await wizard.discover_devices(zigbee_service, known_before=known_before)
    matter_discovered = await wizard.discover_devices(matter_service, known_before=matter_known_before)

    assert [d.id for d in zigbee_discovered] == ["zigbee-light-1"]
    assert [d.id for d in matter_discovered] == ["matter-light-1"]
    assert isinstance(zigbee_discovered[0], DomainDevice)
    assert isinstance(matter_discovered[0], DomainDevice)


# --- "SystemONE-Profil prüfen ... Beta/unsupported klar kennzeichnen" -------


def test_evaluate_compatibility_returns_none_when_unregistered():
    wizard = DeviceOnboardingWizardService()

    result = wizard.evaluate_compatibility(manufacturer="Unknown Corp", model="Widget X", integration_type="zigbee")

    assert result is None


def test_evaluate_compatibility_returns_the_registered_profile():
    profile = DeviceCompatibilityProfile(
        manufacturer="Sonoff", model="ZBDongle-P", integration_type="zigbee", status=CompatibilityStatus.BETA
    )
    register_profile(profile)
    try:
        wizard = DeviceOnboardingWizardService()

        result = wizard.evaluate_compatibility(manufacturer="Sonoff", model="ZBDongle-P", integration_type="zigbee")

        assert result == profile
        assert result.disclaimer is not None
    finally:
        DEVICE_COMPATIBILITY_REGISTRY.clear()
