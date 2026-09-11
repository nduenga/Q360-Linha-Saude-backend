"""Contract test: ROLE_PERMISSIONS must match DOC-001 s18 exactly.

This is deliberately transcribed by hand from the approved matrix rather
than derived from the implementation, so a regression in either direction
(missing or invented grant) is caught.
"""
from __future__ import annotations

from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import ROLE_PERMISSIONS, Permission, Role
from apps.foundation.domain.tenant import TenantId

# Transcribed verbatim from DOC-001 s18 ("Opc." cells excluded).
_EXPECTED: dict[Role, set[Permission]] = {
    Role.ADMIN: {
        Permission.QUOTE_CREATE,
        Permission.QUOTE_EDIT,
        Permission.QUOTE_CALCULATE,
        Permission.QUOTE_SUBMIT,
        Permission.QUOTE_REVIEW,
        Permission.QUOTE_APPROVE,
        Permission.QUOTE_REJECT,
        Permission.PRODUCT_MANAGE,
        Permission.PRICING_CONFIG_MANAGE,
        Permission.AUDIT_READ,
    },
    Role.PRODUCT_CONFIGURATOR: {
        Permission.QUOTE_CREATE,
        Permission.QUOTE_EDIT,
        Permission.QUOTE_CALCULATE,
        Permission.QUOTE_SUBMIT,
        Permission.QUOTE_REVIEW,
        Permission.PRODUCT_MANAGE,
        Permission.PRICING_CONFIG_MANAGE,
    },
    Role.SUBSCRIBER: {
        Permission.QUOTE_CREATE,
        Permission.QUOTE_EDIT,
        Permission.QUOTE_CALCULATE,
        Permission.QUOTE_SUBMIT,
    },
    Role.APPROVER: {
        Permission.QUOTE_CALCULATE,
        Permission.QUOTE_REVIEW,
        Permission.QUOTE_APPROVE,
        Permission.QUOTE_REJECT,
        Permission.AUDIT_READ,
    },
    Role.AUDITOR: {
        Permission.QUOTE_REVIEW,
        Permission.AUDIT_READ,
    },
}


def test_role_permissions_matrix_matches_doc001_s18():
    assert {role: set(perms) for role, perms in ROLE_PERMISSIONS.items()} == _EXPECTED


def test_optional_grants_are_not_hardcoded():
    # "Opc." cells must stay excluded until the Sprint 7 Authority Policy
    # engine exists (ART-009) — regression guard against a well-meaning but
    # premature shortcut.
    assert Permission.QUOTE_CREATE not in ROLE_PERMISSIONS[Role.APPROVER]
    assert Permission.QUOTE_REVIEW not in ROLE_PERMISSIONS[Role.SUBSCRIBER]


def test_actor_permissions_union_multiple_roles():
    actor = Actor(
        actor_id="user-1",
        tenant_id=TenantId.parse("11111111-1111-1111-1111-111111111111"),
        roles=frozenset({Role.APPROVER, Role.AUDITOR}),
    )
    assert actor.has_permission(Permission.QUOTE_APPROVE)
    assert actor.has_permission(Permission.AUDIT_READ)
    assert not actor.has_permission(Permission.PRODUCT_MANAGE)


def test_actor_with_no_roles_has_no_permissions():
    actor = Actor(
        actor_id="user-2",
        tenant_id=TenantId.parse("11111111-1111-1111-1111-111111111111"),
        roles=frozenset(),
    )
    assert actor.permissions == frozenset()
