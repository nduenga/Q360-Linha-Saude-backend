"""Marca pública da seguradora para a app móvel (roadmap_mobile.md, Fase 1 —
pontos 1 e 2). A app é uma só (Q360); depois de saber a seguradora, mostra o
nome, as cores e o logótipo dela. Só sai o que já é público: nada de contas.
"""
from __future__ import annotations

import uuid
from urllib.parse import urlencode

from django.conf import settings

from apps.foundation.application import tenant_status
from apps.foundation.infrastructure.models import Tenant
from apps.platform_admin.application.tenant_settings import module_enabled, settings_of


def app_base_url() -> str:
    """Base das ligações dos emails: o domínio da app (ligações universais) ou,
    sem ele, o portal web."""
    return settings.CUSTOMER_PORTAL_APP_URL or settings.CUSTOMER_PORTAL_URL


def insurer_link(tenant_id: uuid.UUID, *, path: str = "entrar", **query: str) -> str:
    return f"{app_base_url()}/{path}?{urlencode({'seguradora': str(tenant_id), **query})}"


def portal_enabled(tenant: Tenant) -> bool:
    return not tenant_status.is_blocked(tenant.id) and module_enabled(tenant.id, "customerPortal")


def branding_of(tenant: Tenant) -> dict:
    """`hasLogo` em vez do URL: quem responde ao pedido compõe o URL completo."""
    branding = settings_of(tenant)["branding"]
    return {
        "tenantId": str(tenant.id),
        "name": tenant.name,
        "primaryColor": branding.get("primaryColor"),
        "secondaryColor": branding.get("secondaryColor"),
        "hasLogo": bool(branding.get("logo")),
        "portalEnabled": portal_enabled(tenant),
    }


def get_branding(tenant_id: uuid.UUID) -> dict | None:
    tenant = Tenant.objects.filter(id=tenant_id).first()
    return branding_of(tenant) if tenant else None
