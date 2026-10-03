"""Permissões por perfil editáveis pelo negócio (`security.role_permissions`).

O negócio escolhe, por perfil, que permissões do catálogo fixo
(`foundation.domain.permissions.Permission`) esse perfil tem. Não se criam
permissões novas: só se redistribuem as existentes. A versão publicada
substitui as permissões do perfil indicado; os perfis não listados mantêm as
definidas em código.

Proteção contra bloqueio: o perfil ADMIN nunca pode perder
`product:manage` nem `pricing-config:manage` (sem elas ninguém voltaria a
editar a configuração).

O resultado é guardado em cache por inquilino (30 s) e limpo ao publicar ou
retirar uma versão.
"""
from __future__ import annotations

import datetime
from typing import Any

from django.core.cache import cache
from django.db import models

from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.domain.permissions import Permission, Role, register_role_permission_provider

CONFIG_KEY = "security.role_permissions"
PROTECTED = {Role.ADMIN.value: {Permission.PRODUCT_MANAGE.value, Permission.PRICING_CONFIG_MANAGE.value}}
_CACHE_SECONDS = 30
_NONE = "__none__"


def _cache_key(tenant_id) -> str:
    return f"bc:role-permissions:{tenant_id}"


def invalidate(tenant_id) -> None:
    cache.delete(_cache_key(tenant_id))


def parse_rows(rows: Any) -> dict[Role, frozenset[Permission]]:
    result: dict[Role, frozenset[Permission]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            role = Role(row.get("role"))
            granted = {Permission(p) for p in (row.get("permissions") or [])}
        except ValueError:
            continue
        granted |= {Permission(p) for p in PROTECTED.get(role.value, set())}
        result[role] = frozenset(granted)
    return result


def _load(tenant_id) -> dict[Role, frozenset[Permission]]:
    today = datetime.date.today()
    row = (
        BusinessConfiguration.all_tenants.filter(
            tenant_id=tenant_id, config_key=CONFIG_KEY, status="PUBLISHED", effective_from__lte=today
        )
        .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today))
        .order_by("-effective_from", "-version_no")
        .first()
    )
    return parse_rows((row.value_json or {}).get("roles")) if row else {}


def provider(tenant_id) -> dict[Role, frozenset[Permission]] | None:
    key = _cache_key(tenant_id)
    cached = cache.get(key)
    if cached is None:
        try:
            cached = _load(tenant_id) or _NONE
        except RuntimeError:
            # Contexto sem acesso à base de dados (testes unitários puros de
            # domínio): valem as permissões definidas em código.
            return None
        cache.set(key, cached, _CACHE_SECONDS)
    return None if cached == _NONE else cached


def register() -> None:
    register_role_permission_provider(provider)
