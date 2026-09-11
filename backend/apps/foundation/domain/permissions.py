"""Roles and permissions authorised by Q360-MVP-DOC-001 s6 (Actores e
Personas) and s18 (Permissões Funcionais).

Do not add a role or a permission here without a corresponding entry in the
approved functional specification (DOC-000 "Regra de ouro da V1": nenhum
programador deve inventar permissões não definidas nos documentos
autorizadores).
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """DOC-001 s6 — Actores e Personas."""

    ADMIN = "ADMIN"  # Administrador de Tenant
    PRODUCT_CONFIGURATOR = "PRODUCT_CONFIGURATOR"  # Configurador de Produto
    SUBSCRIBER = "SUBSCRIBER"  # Subscritor
    APPROVER = "APPROVER"  # Aprovador
    AUDITOR = "AUDITOR"  # Leitor/Auditor


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
    Role.PRODUCT_CONFIGURATOR: frozenset(
        {
            Permission.QUOTE_CREATE,
            Permission.QUOTE_EDIT,
            Permission.QUOTE_CALCULATE,
            Permission.QUOTE_SUBMIT,
            Permission.QUOTE_REVIEW,
            Permission.PRODUCT_MANAGE,
            Permission.PRICING_CONFIG_MANAGE,
        }
    ),
    Role.SUBSCRIBER: frozenset(
        {
            Permission.QUOTE_CREATE,
            Permission.QUOTE_EDIT,
            Permission.QUOTE_CALCULATE,
            Permission.QUOTE_SUBMIT,
        }
    ),
    Role.APPROVER: frozenset(
        {
            Permission.QUOTE_CALCULATE,
            Permission.QUOTE_REVIEW,
            Permission.QUOTE_APPROVE,
            Permission.QUOTE_REJECT,
            Permission.AUDIT_READ,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.QUOTE_REVIEW,
            Permission.AUDIT_READ,
        }
    ),
}
