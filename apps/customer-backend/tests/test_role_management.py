"""S1V2-02-009 Definition of Done: "Negativtests versuchen Rolleneskalation
über manipulierte API-Aufrufe; alle Wege blockiert und auditierbar"."""

import pytest

from app.audit import InMemoryAuditRecorder
from app.authorization import AuthorizationError
from app.repositories.records import UserRecord
from app.roles import (
    CUSTOMER_ROLE_KEYS,
    PROTECTED_ROLE_KEYS,
    ROLE_PERMISSIONS,
    ProtectedRoleError,
    RoleManagementService,
    UnknownRoleError,
)
from tests.fakes import FakeUnitOfWork, make_actor


@pytest.fixture
def rig():
    uow = FakeUnitOfWork()
    uow.roles.add("member", "role-member-id")
    uow.roles.add("administrator", "role-admin-id")
    uow.users.add(
        UserRecord(
            id="target-user",
            household_id="hh-1",
            role_id="role-member-id",
            display_name="Target User",
            password_hash=None,
            pin_hash=None,
        )
    )
    audit = InMemoryAuditRecorder()
    service = RoleManagementService(uow_factory=lambda: uow, audit=audit)
    return service, uow, audit


async def test_administrator_can_assign_a_customer_role(rig):
    service, uow, audit = rig
    actor = make_actor("users:manage")

    await service.assign_role(actor, target_user_id="target-user", role_key="administrator")

    assert uow.users.get_by_id("target-user").role_id == "role-admin-id"
    assert audit.events[-1]["action"] == "roles.assigned"
    assert audit.events[-1]["metadata"]["role"] == "administrator"


async def test_assign_role_without_permission_is_denied_before_any_check(rig):
    service, uow, audit = rig
    actor = make_actor()  # no users:manage

    with pytest.raises(AuthorizationError):
        await service.assign_role(actor, target_user_id="target-user", role_key="member")

    assert audit.events == []  # denied at the authz gate, nothing to audit as an attempt yet
    assert uow.users.get_by_id("target-user").role_id == "role-member-id"  # unchanged


@pytest.mark.parametrize("protected_role", sorted(PROTECTED_ROLE_KEYS))
async def test_every_protected_role_is_blocked_even_for_an_authorized_actor(rig, protected_role):
    """The core escalation attempt: an actor that legitimately holds
    users:manage (e.g. a compromised admin account, or a client sending a
    hand-crafted request) still cannot assign a protected role."""
    service, uow, audit = rig
    actor = make_actor("users:manage")

    with pytest.raises(ProtectedRoleError):
        await service.assign_role(actor, target_user_id="target-user", role_key=protected_role)

    assert uow.users.get_by_id("target-user").role_id == "role-member-id"  # unchanged
    assert audit.events[-1]["action"] == "roles.assignment_blocked"
    assert audit.events[-1]["outcome"] == "failure"
    assert audit.events[-1]["metadata"]["attemptedRole"] == protected_role
    assert audit.events[-1]["metadata"]["reason"] == "protected_role"


async def test_self_escalation_to_a_protected_role_is_blocked(rig):
    """A user attempting to promote *themselves* to root/service/etc. via a
    manipulated request is blocked the same way as targeting someone else."""
    service, uow, audit = rig
    actor = make_actor("users:manage")
    uow.users.add(
        UserRecord(
            id=actor.user_id,
            household_id="hh-1",
            role_id="role-member-id",
            display_name="Self",
            password_hash=None,
            pin_hash=None,
        )
    )

    with pytest.raises(ProtectedRoleError):
        await service.assign_role(actor, target_user_id=actor.user_id, role_key="root")

    assert uow.users.get_by_id(actor.user_id).role_id == "role-member-id"


async def test_unknown_role_key_is_rejected_not_silently_ignored(rig):
    service, uow, audit = rig
    actor = make_actor("users:manage")

    with pytest.raises(UnknownRoleError):
        await service.assign_role(actor, target_user_id="target-user", role_key="superadmin")

    assert audit.events[-1]["action"] == "roles.assignment_blocked"
    assert audit.events[-1]["metadata"]["reason"] == "unknown_role"


def test_list_assignable_roles_never_includes_a_protected_role(rig):
    service, _uow, _audit = rig
    actor = make_actor("users:manage")

    assignable = service.list_assignable_roles(actor)

    assert assignable == CUSTOMER_ROLE_KEYS
    assert assignable.isdisjoint(PROTECTED_ROLE_KEYS)


def test_service_role_is_least_privilege_among_protected_roles():
    """"Least-privilege Service-Rolle": among the *protected* (internal)
    roles - system/root/pipercat_support are the meaningful comparison
    group, not the customer-facing roles, which serve an unrelated
    purpose (e.g. "display" is intentionally a bare read-only kiosk role
    and is not "more privileged" or "less privileged" than an internal
    service identity in any comparable sense)."""
    service_permission_count = len(ROLE_PERMISSIONS["service"])
    other_protected_roles = PROTECTED_ROLE_KEYS - {"service"}
    assert other_protected_roles, "expected at least one other protected role to compare against"
    for role_key in other_protected_roles:
        permissions = ROLE_PERMISSIONS[role_key]
        assert service_permission_count <= len(permissions), f"'service' is not least-privilege vs '{role_key}'"


def test_no_role_ever_grants_a_wildcard_permission():
    for role_key, permissions in ROLE_PERMISSIONS.items():
        assert "*" not in permissions, f"role '{role_key}' must not grant a wildcard permission"


def test_root_role_exists_but_is_never_in_the_customer_assignable_set():
    """"Volle Root-Rechte nicht als Kundenfeature": root has a defined
    permission set (for internal break-glass tooling outside this
    service) but is categorically excluded from what a customer admin can
    assign."""
    assert "root" in ROLE_PERMISSIONS
    assert "root" not in CUSTOMER_ROLE_KEYS
    assert "root" in PROTECTED_ROLE_KEYS
