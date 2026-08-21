"""Certified/Compatible/Beta device-model compatibility registry
(S1V2-02-026).

Global, product-wide reference data - "the Sonoff Zigbee 3.0 USB Dongle
Plus is Certified" is the same fact on every SystemONE installation, not
something that varies per household. Follows `app/product_class.py`'s
already-established pattern for exactly this kind of SystemONE-wide (not
per-household) classification: a static, code-shipped registry rather
than a database table `apps/customer-backend` (one instance per
household, see docs/product-manifest.md §2) would otherwise need to
duplicate identically across every single customer instance.

"Status kann nicht allein durch Endnutzer auf Certified gesetzt werden"
is satisfied maximally here, not just access-controlled: there is no API
route, database row, or any runtime code path through which a customer
could change an entry at all - the only way to add or change one is a
code change to this file, reviewed and released like any other SystemONE
change. "Testnachweis ist intern dokumentierbar" is exactly what
`CompatibilityTestEvidence` is for: a structured record of what was actually
verified, by whom, when.

`DEVICE_COMPATIBILITY_REGISTRY` starts without a single `CERTIFIED` entry
on purpose: none of the real-hardware validations this registry depends
on (S1V2-02-022 through -025, all currently blocked on physical hardware
access - see their own docs/architecture/*.md files) have actually
happened yet. An empty registry is the honest starting state, not a gap
to paper over with fabricated entries.
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class CompatibilityStatus(str, Enum):
    CERTIFIED = "certified"
    COMPATIBLE = "compatible"
    BETA = "beta"


class CompatibilityTestEvidence(BaseModel):
    """"Certified nur nach realer definierter Testmatrix": a structured
    record of what was actually checked, not a vague claim. `test_matrix`
    keys are test-case names (e.g. "pairing", "on_off",
    "reconnect_after_ha_restart"), values are pass/fail."""

    tested_by: str
    tested_at: date
    test_matrix: dict[str, bool]

    @model_validator(mode="after")
    def _require_at_least_one_test_case(self) -> "CompatibilityTestEvidence":
        if not self.test_matrix:
            raise ValueError("CompatibilityTestEvidence.test_matrix must list at least one real test case")
        return self


class DeviceCompatibilityProfile(BaseModel):
    manufacturer: str
    model: str
    integration_type: str  # e.g. "zigbee", "matter", "shelly", "hue", "generic_ha"
    capabilities: list[str] = Field(default_factory=list)
    status: CompatibilityStatus
    test_evidence: CompatibilityTestEvidence | None = None

    @model_validator(mode="after")
    def _certified_requires_a_fully_passing_test_matrix(self) -> "DeviceCompatibilityProfile":
        if self.status is CompatibilityStatus.CERTIFIED:
            if self.test_evidence is None:
                raise ValueError(
                    'Certified status requires CompatibilityTestEvidence (S1V2-02-026: "nur nach realer definierter Testmatrix")'
                )
            if not all(self.test_evidence.test_matrix.values()):
                raise ValueError("Certified status requires every recorded test case to have passed")
        return self

    @property
    def disclaimer(self) -> str | None:
        """"Beta ausdrücklich mit Hinweis und ohne Gleichstellung" -
        computed, never a settable field, so a Beta entry can never
        silently lose its warning and a Certified/Compatible entry can
        never carry a stray one."""
        if self.status is CompatibilityStatus.BETA:
            return (
                "Beta: Diese Kombination wurde noch nicht vollständig getestet. "
                "Funktioniert möglicherweise nicht zuverlässig und wird nicht als "
                "gleichwertig zu Certified/Compatible behandelt."
            )
        return None


def _key(manufacturer: str, model: str, integration_type: str) -> tuple[str, str, str]:
    return (manufacturer.strip().lower(), model.strip().lower(), integration_type.strip().lower())


DEVICE_COMPATIBILITY_REGISTRY: dict[tuple[str, str, str], DeviceCompatibilityProfile] = {}


def register_profile(profile: DeviceCompatibilityProfile) -> None:
    """The only sanctioned way an entry is added - a code change to this
    module (calling this at import time, see below), never something a
    request handler or customer input invokes."""
    DEVICE_COMPATIBILITY_REGISTRY[_key(profile.manufacturer, profile.model, profile.integration_type)] = profile


def lookup_compatibility(manufacturer: str, model: str, integration_type: str) -> DeviceCompatibilityProfile | None:
    return DEVICE_COMPATIBILITY_REGISTRY.get(_key(manufacturer, model, integration_type))


# --- Registered profiles ----------------------------------------------------
#
# Empty for now - see this module's docstring. Add entries here, each with
# real CompatibilityTestEvidence, once a real-hardware validation (S1V2-02-022 through
# -025 or a future device) actually completes.
