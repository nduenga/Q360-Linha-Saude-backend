"""Definições de cada seguradora geridas pela plataforma (`tenant.settings_json`).

- `suspension`: motivo, data de reativação (opcional), quem e quando suspendeu.
- `branding`: cores e logótipo, usados nas propostas e nos emails quando a
  seguradora ainda não publicou a sua própria identidade visual.
- `limits`: número máximo de utilizadores e módulos ativos.

Os valores por omissão (`DEFAULTS`) mantêm o comportamento de antes: sem
limite de utilizadores e todos os módulos ligados."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from django.conf import settings as django_settings
from django.core.cache import cache

from apps.foundation.infrastructure.models import Tenant

MODULES = {
    "customerPortal": "Portal do Cliente",
}
DEFAULTS: dict[str, Any] = {
    "suspension": None,
    "branding": {"primaryColor": None, "secondaryColor": None, "logo": None},
    "limits": {"maxUsers": None, "modules": {key: True for key in MODULES}},
}
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
LOGO_TYPES = {"image/png": "png", "image/jpeg": "jpg"}
MAX_LOGO_BYTES = 1024 * 1024
_CACHE_SECONDS = 30


class TenantSettingsError(ValueError):
    pass


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def settings_of(tenant: Tenant) -> dict[str, Any]:
    return _merge(DEFAULTS, tenant.settings_json or {})


def public_settings(tenant: Tenant) -> dict[str, Any]:
    """O que a API mostra: o logótipo como «tem / não tem», nunca o caminho no disco."""
    data = settings_of(tenant)
    logo = data["branding"].pop("logo", None)
    data["branding"]["hasLogo"] = bool(logo)
    data["limits"]["moduleLabels"] = dict(MODULES)
    return data


def _cache_key(tenant_id) -> str:
    return f"tenant-settings:{tenant_id}"


def invalidate(tenant_id) -> None:
    cache.delete(_cache_key(tenant_id))


def _cached(tenant_id) -> dict[str, Any]:
    data = cache.get(_cache_key(tenant_id))
    if data is None:
        try:
            tenant = Tenant.objects.filter(id=tenant_id).first()
        except RuntimeError:  # sem acesso à base de dados (testes unitários)
            return copy.deepcopy(DEFAULTS)
        data = settings_of(tenant) if tenant else copy.deepcopy(DEFAULTS)
        cache.set(_cache_key(tenant_id), data, _CACHE_SECONDS)
    return data


def module_enabled(tenant_id, module: str) -> bool:
    return bool(_cached(tenant_id)["limits"]["modules"].get(module, True))


def max_users(tenant_id) -> int | None:
    value = _cached(tenant_id)["limits"].get("maxUsers")
    return int(value) if value else None


def validate_branding(branding: dict[str, Any]) -> dict[str, Any]:
    clean = {}
    for key in ("primaryColor", "secondaryColor"):
        if key in branding:
            value = (branding.get(key) or "").strip() or None
            if value is not None and not _COLOR.match(value):
                raise TenantSettingsError("As cores usam o formato #RRGGBB (ex.: #0B3D91).")
            clean[key] = value.upper() if value else None
    return clean


def validate_limits(limits: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    if "maxUsers" in limits:
        value = limits.get("maxUsers")
        if value in (None, "", 0):
            clean["maxUsers"] = None
        else:
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise TenantSettingsError("O número máximo de utilizadores tem de ser um número inteiro.") from exc
            if number < 1:
                raise TenantSettingsError("O número máximo de utilizadores tem de ser pelo menos 1.")
            clean["maxUsers"] = number
    if "modules" in limits:
        modules = limits.get("modules") or {}
        unknown = set(modules) - set(MODULES)
        if unknown:
            raise TenantSettingsError(f"Módulos desconhecidos: {sorted(unknown)}")
        clean["modules"] = {key: bool(value) for key, value in modules.items()}
    return clean


def logo_path(tenant: Tenant) -> Path | None:
    key = settings_of(tenant)["branding"].get("logo")
    if not key:
        return None
    path = Path(django_settings.MEDIA_ROOT) / key
    return path if path.exists() else None


def logo_bytes(tenant_id) -> tuple[bytes, str] | None:
    tenant = Tenant.objects.filter(id=tenant_id).first()
    path = logo_path(tenant) if tenant else None
    if path is None:
        return None
    content_type = "image/png" if path.suffix == ".png" else "image/jpeg"
    return path.read_bytes(), content_type


def store_logo(tenant: Tenant, data: bytes, content_type: str) -> str:
    if content_type not in LOGO_TYPES:
        raise TenantSettingsError("O logótipo tem de ser PNG ou JPEG.")
    if len(data) > MAX_LOGO_BYTES:
        raise TenantSettingsError("O logótipo não pode ter mais de 1 MB.")
    signature_ok = data.startswith(b"\x89PNG") if content_type == "image/png" else data.startswith(b"\xff\xd8")
    if not signature_ok:
        raise TenantSettingsError("O ficheiro não é uma imagem PNG ou JPEG válida.")
    key = f"platform/tenant-logos/{tenant.id}.{LOGO_TYPES[content_type]}"
    path = Path(django_settings.MEDIA_ROOT) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    for old in path.parent.glob(f"{tenant.id}.*"):
        old.unlink(missing_ok=True)
    path.write_bytes(data)
    return key


def tenant_branding(tenant_id) -> dict[str, Any] | None:
    """Identidade visual da ficha da seguradora no formato de `branding_from`
    (company/color/tagline/footer), para propostas e relatórios."""
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return None
    branding = settings_of(tenant)["branding"]
    if not branding.get("primaryColor") and not branding.get("logo"):
        return None
    return {"company": tenant.name, "color": branding.get("primaryColor"), "tagline": None, "footer": None,
            "configurationId": None, "tenantLogo": True}
