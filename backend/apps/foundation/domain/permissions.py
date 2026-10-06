"""Roles and permissions authorised by Q360-MVP-DOC-001 s6 (Actores e
Personas) and s18 (Permissões Funcionais).

Do not add a role or a permission here without a corresponding entry in the
approved functional specification (DOC-000 "Regra de ouro da V1": nenhum
programador deve inventar permissões não definidas nos documentos
autorizadores).
"""
from __future__ import annotations

from enum import Enum

from apps.foundation.domain.scopes import Scope


class Role(str, Enum):
    """DOC-001 s6 — Actores e Personas."""

    PLATFORM_ADMIN = "PLATFORM_ADMIN"  # Administrador global da plataforma
    ADMIN = "ADMIN"  # Administrador do tenant: tudo, incluindo contas de utilizadores
    SUBSCRIPTION_MANAGER = "SUBSCRIPTION_MANAGER"  # Gestor de subscrição: configuração + aprovação + auditoria
    SUBSCRIBER = "SUBSCRIBER"  # Subscritor: cotações, elegibilidade e decisão (aprovar/reprovar)


# Perfis antigos que deixaram de existir: o Aprovador, o Auditor e o
# Configurador de Produto passaram a Gestor de subscrição. Aceitam-se nos
# tokens ainda em circulação durante a transição.
LEGACY_ROLE_ALIASES: dict[str, "Role"] = {
    "PRODUCT_CONFIGURATOR": Role.SUBSCRIPTION_MANAGER,
    "APPROVER": Role.SUBSCRIPTION_MANAGER,
    "AUDITOR": Role.SUBSCRIPTION_MANAGER,
}


class Permission(str, Enum):
    """DOC-001 s18 — Permissões Funcionais (column headers)."""

    QUOTE_CREATE = "quote:create"
    QUOTE_EDIT = "quote:edit"
    QUOTE_CALCULATE = "quote:calculate"
    QUOTE_SUBMIT = "quote:submit"
    QUOTE_REVIEW = "quote:review"
    QUOTE_APPROVE = "quote:approve"
    QUOTE_REJECT = "quote:reject"
    PRODUCT_MANAGE = "product:manage"
    PRICING_CONFIG_MANAGE = "pricing-config:manage"
    AUDIT_READ = "audit:read"


# DOC-001 s18 permission matrix, unconditional grants ("✓") only.
#
# Cells marked "Opc." in DOC-001 (permitted only when explicitly configured
# by the authority matrix) are deliberately NOT included below: that
# behaviour belongs to the Authority Policy engine (Sprint 7, ART-009) and
# must not be approximated with a hardcoded guess before it exists.
#   - quote:create for Aprovador -> Opc. (excluded)
#   - quote:review for Subscritor -> Opc. (excluded)
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(
        {
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
        }
    ),
    # Gestor de subscrição = tudo o que o Configurador de Produto fazia, mais o
    # que faziam o Aprovador e o Auditor (que deixam de existir).
    Role.SUBSCRIPTION_MANAGER: frozenset(
        {
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
        }
    ),
    # Subscritor: o que já fazia (criar, editar, calcular, submeter), mais
    # decidir uma cotação (aprovar/reprovar, com a fila de revisão que isso
    # exige). A elegibilidade já só depende do escopo de escrita. A regra dos
    # quatro olhos mantém-se: ninguém decide a cotação que submeteu.
    Role.SUBSCRIBER: frozenset(
        {
            Permission.QUOTE_CREATE,
            Permission.QUOTE_EDIT,
            Permission.QUOTE_CALCULATE,
            Permission.QUOTE_SUBMIT,
            Permission.QUOTE_REVIEW,
            Permission.QUOTE_APPROVE,
            Permission.QUOTE_REJECT,
        }
    ),
}

# Canonical Role -> ART-006 OAuth2 scope mapping (domain/scopes.py). Before
# apps.staff_accounts existed, this was duplicated ad hoc across 3 users in
# apps.foundation.interfaces.auth_views.DevLoginView; this is now the one
# source of truth, used by StaffAccountAuthService when it issues a token.
# Derived from ROLE_PERMISSIONS above: q360.write/approve/admin/audit map
# to the write/approve/product-or-pricing-config/audit-read permissions a
# role actually has; q360.read is granted to every role (DOC-001 s18 - a
# role with any permission at all can at minimum read).
ROLE_SCOPES: dict[Role, frozenset[Scope]] = {
    Role.ADMIN: frozenset({Scope.READ, Scope.WRITE, Scope.ADMIN, Scope.APPROVE, Scope.AUDIT}),
    Role.SUBSCRIPTION_MANAGER: frozenset({Scope.READ, Scope.WRITE, Scope.ADMIN, Scope.APPROVE, Scope.AUDIT}),
    Role.SUBSCRIBER: frozenset({Scope.READ, Scope.WRITE, Scope.APPROVE}),
}


# Fornecedor opcional de permissões por perfil editadas pelo negócio
# (`security.role_permissions`). Registado pela aplicação business_config no
# arranque; foundation nunca depende dela (DOC-004 s3.1). Recebe o id do
# inquilino e devolve {Role: frozenset[Permission]} (só os perfis alterados)
# ou None.
_ROLE_PERMISSION_OVERRIDES: list = []


def register_role_permission_provider(provider) -> None:
    _ROLE_PERMISSION_OVERRIDES[:] = [provider]


def effective_role_permissions(tenant_id) -> dict[Role, frozenset[Permission]]:
    """Permissões de cada perfil: as de `ROLE_PERMISSIONS` com as alterações
    publicadas pelo negócio para o inquilino por cima."""
    merged = dict(ROLE_PERMISSIONS)
    if _ROLE_PERMISSION_OVERRIDES and tenant_id is not None:
        merged.update(_ROLE_PERMISSION_OVERRIDES[0](tenant_id) or {})
    return merged


def scopes_for_permissions(permissions: frozenset[Permission]) -> frozenset[Scope]:
    """Escopos OAuth2 que as permissões de um perfil justificam (mesma regra
    que deu origem a `ROLE_SCOPES`)."""
    scopes = {Scope.READ}
    if permissions & {
        Permission.QUOTE_CREATE, Permission.QUOTE_EDIT, Permission.QUOTE_CALCULATE, Permission.QUOTE_SUBMIT,
        Permission.PRODUCT_MANAGE, Permission.PRICING_CONFIG_MANAGE,
    }:
        scopes.add(Scope.WRITE)
    if permissions & {Permission.QUOTE_APPROVE, Permission.QUOTE_REJECT}:
        scopes.add(Scope.APPROVE)
    if permissions & {Permission.PRODUCT_MANAGE, Permission.PRICING_CONFIG_MANAGE}:
        scopes.add(Scope.ADMIN)
    if Permission.AUDIT_READ in permissions:
        scopes.add(Scope.AUDIT)
    return frozenset(scopes)


def scopes_for_roles(roles: frozenset[Role], tenant_id=None) -> frozenset[Scope]:
    if tenant_id is not None and _ROLE_PERMISSION_OVERRIDES:
        effective = effective_role_permissions(tenant_id)
        granted_scopes: set[Scope] = set()
        for role in roles:
            granted_scopes |= scopes_for_permissions(effective.get(role, frozenset()))
        return frozenset(granted_scopes)
    granted: set[Scope] = set()
    for role in roles:
        granted |= ROLE_SCOPES.get(role, frozenset())
    return frozenset(granted)
