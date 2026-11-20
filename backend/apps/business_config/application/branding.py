"""Identidade visual dos documentos (`proposal.branding`).

O negócio publica o nome da empresa, a cor principal, o lema e o rodapé, e
anexa o logótipo (documento do tipo LOGO) à própria versão da configuração.
Sem configuração publicada os documentos mantêm o desenho por omissão.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.business_config.application.readers import BusinessSnapshot
from apps.business_config.infrastructure.models import BusinessConfigurationDocument

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
LOGO_TYPE = "LOGO"
_MAX_LOGO_BYTES = 2 * 1024 * 1024


def _tenant_fallback() -> dict[str, Any] | None:
    """Sem `proposal.branding` publicada: as cores e o logótipo que a
    plataforma registou na ficha da seguradora."""
    from apps.foundation.application.context import CurrentTenantProvider
    from apps.platform_admin.application.tenant_settings import tenant_branding

    tenant_id = CurrentTenantProvider.get()
    return tenant_branding(tenant_id.value) if tenant_id is not None else None


def branding_from(snapshot: BusinessSnapshot) -> dict[str, Any] | None:
    value = snapshot.get("proposal.branding")
    if not value:
        return _tenant_fallback()
    color = str(value.get("primary_color") or "")
    return {
        "company": str(value.get("company_name") or "").strip() or None,
        "color": color if _COLOR.match(color) else None,
        "tagline": str(value.get("tagline") or "").strip() or None,
        "footer": str(value.get("footer_text") or "").strip() or None,
        "configurationId": (snapshot.versions.get("proposal.branding") or {}).get("configurationId"),
    }


def load_logo(branding: dict[str, Any] | None) -> bytes | None:
    """Bytes do logótipo anexado à versão publicada (PNG/JPEG), se existir;
    sem logótipo na configuração, o da ficha da seguradora."""
    if not branding:
        return None
    if not branding.get("configurationId"):
        return _tenant_logo()
    document = (
        BusinessConfigurationDocument.objects.filter(configuration_id=branding["configurationId"], document_type=LOGO_TYPE)
        .order_by("-created_at")
        .first()
    )
    if document is None or (document.content_type or "") not in ("image/png", "image/jpeg"):
        return _tenant_logo()
    path = Path(settings.MEDIA_ROOT) / document.storage_key
    if not path.exists() or path.stat().st_size > _MAX_LOGO_BYTES:
        return None
    return path.read_bytes()


def _tenant_logo() -> bytes | None:
    from apps.foundation.application.context import CurrentTenantProvider
    from apps.platform_admin.application.tenant_settings import logo_bytes

    tenant_id = CurrentTenantProvider.get()
    found = logo_bytes(tenant_id.value) if tenant_id is not None else None
    return found[0] if found else None
