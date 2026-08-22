"""S1V2-02-026 Definition of Done: "Status kann nicht allein durch
Endnutzer auf Certified gesetzt werden; Testnachweis ist intern
dokumentierbar."

No permission/Actor machinery here on purpose (see
app/device_compatibility.py's docstring): the registry is static,
code-shipped reference data with no runtime write path at all - the
strongest possible reading of "kann nicht durch Endnutzer gesetzt
werden", stronger than a permission check a customer could at least
attempt and be denied. These tests instead verify the two structural
guarantees that *do* have runtime behavior: Certified requires a real,
fully-passing CompatibilityTestEvidence, and Beta always carries its disclaimer.
"""

import pytest
from pydantic import ValidationError

from app.device_compatibility import (
    CompatibilityStatus,
    CompatibilityTestEvidence,
    DeviceCompatibilityProfile,
    lookup_compatibility,
    register_profile,
)


def _passing_evidence() -> CompatibilityTestEvidence:
    return CompatibilityTestEvidence(tested_by="qa-team", tested_at="2026-08-21", test_matrix={"pairing": True, "on_off": True})


# --- Certified requires real, fully-passing test evidence -------------------


def test_certified_without_test_evidence_is_rejected():
    with pytest.raises(ValidationError, match="Testmatrix"):
        DeviceCompatibilityProfile(
            manufacturer="Sonoff", model="ZBDongle-P", integration_type="zigbee", status=CompatibilityStatus.CERTIFIED
        )


def test_certified_with_a_failing_test_case_is_rejected():
    evidence = CompatibilityTestEvidence(tested_by="qa-team", tested_at="2026-08-21", test_matrix={"pairing": True, "reconnect": False})
    with pytest.raises(ValidationError, match="every recorded test case"):
        DeviceCompatibilityProfile(
            manufacturer="Sonoff",
            model="ZBDongle-P",
            integration_type="zigbee",
            status=CompatibilityStatus.CERTIFIED,
            test_evidence=evidence,
        )


def test_certified_with_a_fully_passing_test_matrix_is_accepted():
    profile = DeviceCompatibilityProfile(
        manufacturer="Sonoff",
        model="ZBDongle-P",
        integration_type="zigbee",
        status=CompatibilityStatus.CERTIFIED,
        test_evidence=_passing_evidence(),
    )
    assert profile.status is CompatibilityStatus.CERTIFIED


def test_compatible_and_beta_do_not_require_test_evidence():
    DeviceCompatibilityProfile(manufacturer="X", model="Y", integration_type="generic_ha", status=CompatibilityStatus.COMPATIBLE)
    DeviceCompatibilityProfile(manufacturer="X", model="Y", integration_type="generic_ha", status=CompatibilityStatus.BETA)


def test_test_evidence_requires_at_least_one_test_case():
    with pytest.raises(ValidationError, match="at least one real test case"):
        CompatibilityTestEvidence(tested_by="qa-team", tested_at="2026-08-21", test_matrix={})


# --- Beta disclaimer: computed, never settable, never missing ---------------


def test_beta_status_always_carries_a_disclaimer():
    profile = DeviceCompatibilityProfile(manufacturer="X", model="Y", integration_type="generic_ha", status=CompatibilityStatus.BETA)
    assert profile.disclaimer is not None
    assert "nicht" in profile.disclaimer.lower()


def test_certified_and_compatible_never_carry_a_disclaimer():
    certified = DeviceCompatibilityProfile(
        manufacturer="X", model="Y", integration_type="generic_ha", status=CompatibilityStatus.CERTIFIED, test_evidence=_passing_evidence()
    )
    compatible = DeviceCompatibilityProfile(manufacturer="X", model="Y", integration_type="generic_ha", status=CompatibilityStatus.COMPATIBLE)
    assert certified.disclaimer is None
    assert compatible.disclaimer is None


def test_disclaimer_is_a_read_only_property_ignoring_any_constructor_kwarg():
    """`disclaimer` is a computed `@property`, not a Pydantic field - a
    constructor kwarg of the same name is silently dropped (Pydantic's
    default `extra="ignore"`), so the real, status-derived text is always
    what callers see, never something a caller could override."""
    profile = DeviceCompatibilityProfile(
        manufacturer="X", model="Y", integration_type="generic_ha", status=CompatibilityStatus.BETA, disclaimer="custom text"
    )
    assert profile.disclaimer != "custom text"
    assert "nicht" in profile.disclaimer.lower()


# --- registry lookup ----------------------------------------------------------


def test_lookup_returns_none_for_an_unregistered_device():
    assert lookup_compatibility("Nonexistent Corp", "Model Z", "generic_ha") is None


def test_lookup_is_case_and_whitespace_insensitive(monkeypatch):
    profile = DeviceCompatibilityProfile(
        manufacturer="Sonoff", model="ZBDongle-P", integration_type="zigbee", status=CompatibilityStatus.BETA
    )
    register_profile(profile)
    try:
        assert lookup_compatibility("  SONOFF  ", "zbdongle-p", "ZIGBEE") == profile
    finally:
        from app.device_compatibility import DEVICE_COMPATIBILITY_REGISTRY

        DEVICE_COMPATIBILITY_REGISTRY.clear()
