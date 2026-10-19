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
        Permission.QUOTE_DISCOUNT_APPROVE,
    },
    # Gestor de subscrição = Configurador + Aprovador + Auditor (que deixaram de existir).
    Role.SUBSCRIPTION_MANAGER: {
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
    # Subscritor: cria/edita/calcula/submete e decide (aprovar/reprovar).
    Role.SUBSCRIBER: {
        Permission.QUOTE_CREATE,
        Permission.QUOTE_EDIT,
        Permission.QUOTE_CALCULATE,
        Permission.QUOTE_SUBMIT,
        Permission.QUOTE_REVIEW,
        Permission.QUOTE_APPROVE,
        Permission.QUOTE_REJECT,
    },
    Role.TECHNICAL_DIRECTOR: {Permission.QUOTE_DISCOUNT_APPROVE},
}


def test_role_permissions_matrix_matches_doc001_s18():
    assert {role: set(perms) for role, perms in ROLE_PERMISSIONS.items()} == _EXPECTED


def test_discount_approval_is_limited_to_admin_and_technical_director():
    everything = set(Permission)
    assert ROLE_PERMISSIONS[Role.ADMIN] == everything
    assert ROLE_PERMISSIONS[Role.SUBSCRIPTION_MANAGER] == everything - {Permission.QUOTE_DISCOUNT_APPROVE}
    assert ROLE_PERMISSIONS[Role.TECHNICAL_DIRECTOR] == {Permission.QUOTE_DISCOUNT_APPROVE}
    assert Permission.QUOTE_DISCOUNT_APPROVE not in ROLE_PERMISSIONS[Role.SUBSCRIBER]
    assert Permission.PRODUCT_MANAGE not in ROLE_PERMISSIONS[Role.SUBSCRIBER]
    assert Permission.PRICING_CONFIG_MANAGE not in ROLE_PERMISSIONS[Role.SUBSCRIBER]
    assert Permission.AUDIT_READ not in ROLE_PERMISSIONS[Role.SUBSCRIBER]


def test_legacy_roles_map_to_the_subscription_manager():
    from apps.foundation.domain.permissions import LEGACY_ROLE_ALIASES

    assert set(LEGACY_ROLE_ALIASES) == {"PRODUCT_CONFIGURATOR", "APPROVER", "AUDITOR"}
    assert set(LEGACY_ROLE_ALIASES.values()) == {Role.SUBSCRIPTION_MANAGER}


def test_scopes_follow_the_permissions():
    from apps.foundation.domain.permissions import scopes_for_roles
    from apps.foundation.domain.scopes import Scope

    assert Scope.APPROVE in scopes_for_roles(frozenset({Role.SUBSCRIBER}))
    assert Scope.ADMIN not in scopes_for_roles(frozenset({Role.SUBSCRIBER}))
    assert {Scope.ADMIN, Scope.APPROVE, Scope.AUDIT} <= scopes_for_roles(frozenset({Role.SUBSCRIPTION_MANAGER}))


def test_actor_permissions_union_multiple_roles():
    actor = Actor(
        actor_id="user-1",
        tenant_id=TenantId.parse("11111111-1111-1111-1111-111111111111"),
        roles=frozenset({Role.SUBSCRIBER}),
    )
    assert actor.has_permission(Permission.QUOTE_APPROVE)
    assert not actor.has_permission(Permission.AUDIT_READ)
    assert not actor.has_permission(Permission.PRODUCT_MANAGE)


def test_actor_with_no_roles_has_no_permissions():
    actor = Actor(
        actor_id="user-2",
        tenant_id=TenantId.parse("11111111-1111-1111-1111-111111111111"),
        roles=frozenset(),
    )
    assert actor.permissions == frozenset()
