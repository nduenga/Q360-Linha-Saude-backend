"""Modelos de partida do fornecedor (camada geral, sem tenant).

Um modelo é um conjunto de configurações de negócio do catálogo
(`content.configurations = {configKey: valor}`), validadas como qualquer
configuração do tenant. Um modelo de produto pode ainda pedir os produtos e
planos de mercado (`content.marketProducts = true`, os do PDF «Coberturas e
Capitais»).

Ciclo: uma conta da plataforma propõe uma versão, outra aprova. O tenant vê
só a versão publicada mais recente e adota-a: cada configuração é COPIADA
para um rascunho do tenant (nunca ligada ao modelo), que segue o ciclo normal
de submissão e aprovação. Mudar o modelo depois não altera o que um tenant já
adotou."""
from __future__ import annotations

import datetime
import re
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.business_config.application.service import create_configuration, validate
from apps.business_config.domain.catalog import CATALOG_BY_KEY
from apps.business_config.domain.errors import InvalidConfiguration
from apps.foundation.application.change_audit import require_reason
from apps.foundation.application.platform_parameter_service import (
    PlatformFourEyesError,
    PlatformParameterStateError,
    UnknownPlatformParameterError,
)
from apps.foundation.infrastructure.models import PlatformTemplateVersion as Version

KINDS = ("PRODUCT", "ACTUARIAL_MODEL", "FORMULA_SET", "COVERAGE_LIBRARY")
KIND_LABELS = {
    "PRODUCT": "Produto de mercado",
    "ACTUARIAL_MODEL": "Modelo actuarial de referência",
    "FORMULA_SET": "Conjunto de fórmulas",
    "COVERAGE_LIBRARY": "Biblioteca de coberturas",
}
# Chaves que cada tipo de modelo pode trazer (as restantes são recusadas).
KIND_KEYS = {
    "PRODUCT": None,  # qualquer chave do catálogo
    "ACTUARIAL_MODEL": {"pricing.actuarial_model", "pricing.fractionation"},
    "FORMULA_SET": {"pricing.formulas"},
    "COVERAGE_LIBRARY": {"product.coverages", "product.capitals_sublimits", "product.waiting_periods",
                         "product.exclusions", "product.member_participation"},
}
SEGMENTS = ("SAU", "SAG")
_CODE = re.compile(r"^[a-z][a-z0-9_-]{0,59}$")


class TemplateContentError(InvalidConfiguration):
    pass


def validate_content(kind: str, content: Any) -> dict[str, Any]:
    if kind not in KINDS:
        raise TemplateContentError(f"Tipo de modelo inválido (use {list(KINDS)})")
    if not isinstance(content, dict):
        raise TemplateContentError("O conteúdo do modelo tem de ser um objeto")
    unknown = set(content) - {"configurations", "marketProducts"}
    if unknown:
        raise TemplateContentError(f"Secções desconhecidas no modelo: {sorted(unknown)}")
    configurations = content.get("configurations") or {}
    if not isinstance(configurations, dict):
        raise TemplateContentError("'configurations' tem de ser um objeto {configKey: valor}")
    market = content.get("marketProducts", False)
    if not isinstance(market, bool):
        raise TemplateContentError("'marketProducts' tem de ser verdadeiro ou falso")
    if market and kind != "PRODUCT":
        raise TemplateContentError("Só um modelo de produto pode criar os produtos de mercado")
    if not configurations and not market:
        raise TemplateContentError("O modelo não tem nada para adotar")
    allowed = KIND_KEYS[kind]
    for key, value in configurations.items():
        if key not in CATALOG_BY_KEY:
            raise TemplateContentError(f"'{key}' não é uma configuração do catálogo")
        if allowed is not None and key not in allowed:
            raise TemplateContentError(f"Um modelo {kind} não pode trazer '{key}' (permitidas: {sorted(allowed)})")
        try:
            validate(key, value)
        except InvalidConfiguration as exc:
            raise TemplateContentError(f"{key}: {exc}") from exc
    return {"configurations": configurations, "marketProducts": market}


def latest_published(code: str) -> Version | None:
    return Version.objects.filter(code=code, status=Version.PUBLISHED).order_by("-version_no").first()


def version_payload(v: Version, *, with_content: bool = False, latest_no: int | None = None) -> dict[str, Any]:
    content = v.content_json or {}
    payload = {
        "code": v.code,
        "versionNo": v.version_no,
        "status": v.status,
        "kind": v.kind,
        "kindLabel": KIND_LABELS.get(v.kind, v.kind),
        "name": v.name,
        "description": v.description,
        "segment": v.segment,
        "configKeys": sorted((content.get("configurations") or {})),
        "marketProducts": bool(content.get("marketProducts")),
        "source": v.source,
        "isLatestPublished": latest_no is not None and v.version_no == latest_no,
        "reason": v.reason,
        "createdBy": v.created_by,
        "createdAt": v.created_at.isoformat() if v.created_at else None,
        "decidedBy": v.decided_by,
        "decidedAt": v.decided_at.isoformat() if v.decided_at else None,
        "decisionNote": v.decision_note,
    }
    if with_content:
        payload["content"] = content
    return payload


def list_published() -> list[dict[str, Any]]:
    """O que os tenants veem: a versão publicada mais recente de cada modelo."""
    result = []
    for code in sorted(set(Version.objects.filter(status=Version.PUBLISHED).values_list("code", flat=True))):
        v = latest_published(code)
        result.append(version_payload(v, latest_no=v.version_no))
    return result


def list_all() -> list[dict[str, Any]]:
    result = []
    for code in sorted(set(Version.objects.values_list("code", flat=True))):
        current = latest_published(code)
        pending = Version.objects.filter(code=code, status=Version.PENDING_APPROVAL).order_by("version_no")
        latest = current or Version.objects.filter(code=code).order_by("-version_no").first()
        result.append({
            "code": code, "name": latest.name, "kind": latest.kind,
            "published": version_payload(current, latest_no=current.version_no) if current else None,
            "pendingVersions": [version_payload(p) for p in pending],
        })
    return result


def describe(code: str, *, published_only: bool = False) -> dict[str, Any]:
    current = latest_published(code)
    if published_only:
        if current is None:
            raise UnknownPlatformParameterError(f"O modelo '{code}' não existe ou não tem versão publicada")
        return version_payload(current, with_content=True, latest_no=current.version_no)
    if current is None and not Version.objects.filter(code=code).exists():
        raise UnknownPlatformParameterError(f"Modelo '{code}' desconhecido")
    return {
        "code": code,
        "published": version_payload(current, with_content=True, latest_no=current.version_no) if current else None,
        "pendingVersions": [version_payload(p, with_content=True)
                            for p in Version.objects.filter(code=code, status=Version.PENDING_APPROVAL)],
    }


def list_versions(code: str) -> list[dict[str, Any]]:
    current = latest_published(code)
    versions = Version.objects.filter(code=code).order_by("-version_no")
    if not versions.exists():
        raise UnknownPlatformParameterError(f"Modelo '{code}' desconhecido")
    return [version_payload(v, latest_no=current.version_no if current else None) for v in versions]


def propose(*, code: str, kind: str, name: str, content: Any, reason: str | None, actor_id: str,
            description: str | None = None, segment: str | None = None, source: str | None = None) -> dict[str, Any]:
    reason = require_reason(reason)
    if not isinstance(code, str) or not _CODE.match(code):
        raise TemplateContentError("O código do modelo usa minúsculas, números, '-' e '_' (ex.: saude-sau-referencia)")
    if not isinstance(name, str) or not name.strip():
        raise TemplateContentError("Indique o nome do modelo")
    if segment is not None and segment not in SEGMENTS:
        raise TemplateContentError(f"Segmento inválido (use {list(SEGMENTS)})")
    clean = validate_content(kind, content)
    with transaction.atomic():
        list(Version.objects.select_for_update().filter(code=code).values_list("id", flat=True))
        if Version.objects.filter(code=code, status=Version.PENDING_APPROVAL).exists():
            raise PlatformParameterStateError(f"O modelo '{code}' já tem uma versão à espera de aprovação")
        previous = Version.objects.filter(code=code).order_by("-version_no").first()
        if previous is not None and previous.kind != kind:
            raise TemplateContentError(f"O modelo '{code}' é do tipo {previous.kind}; não pode mudar de tipo")
        last = Version.objects.filter(code=code).aggregate(m=Max("version_no"))["m"] or 0
        version = Version.objects.create(
            code=code, version_no=last + 1, kind=kind, name=name.strip(),
            description=(description or "").strip() or None, segment=segment, content_json=clean,
            source=(source or "").strip() or None, reason=reason, created_by=actor_id,
        )
    return version_payload(version)


def _pending(code: str, version_no: int) -> Version:
    version = Version.objects.select_for_update().filter(code=code, version_no=version_no).first()
    if version is None:
        raise UnknownPlatformParameterError(f"O modelo '{code}' não tem a versão {version_no}")
    if version.status != Version.PENDING_APPROVAL:
        raise PlatformParameterStateError(f"A versão {version_no} do modelo '{code}' já foi decidida ({version.status})")
    return version


def approve(*, code: str, version_no: int, actor_id: str, note: str | None = None) -> dict[str, Any]:
    with transaction.atomic():
        version = _pending(code, version_no)
        if version.created_by == actor_id:
            raise PlatformFourEyesError("Quem propôs a versão não a pode aprovar: tem de ser outra conta da plataforma")
        version.status = Version.PUBLISHED
        version.decided_by = actor_id
        version.decided_at = timezone.now()
        version.decision_note = (note or "").strip() or None
        version.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    return version_payload(version)


def reject(*, code: str, version_no: int, actor_id: str, note: str | None) -> dict[str, Any]:
    note = require_reason(note)
    with transaction.atomic():
        version = _pending(code, version_no)
        version.status = Version.REJECTED
        version.decided_by = actor_id if actor_id != version.created_by else None
        version.decided_at = timezone.now()
        version.decision_note = note
        version.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    return version_payload(version)


@transaction.atomic
def adopt(request, *, code: str, effective_from: datetime.date | None = None) -> dict[str, Any]:
    """Copia a versão publicada do modelo para rascunhos do tenant."""
    version = latest_published(code)
    if version is None:
        raise UnknownPlatformParameterError(f"O modelo '{code}' não existe ou não tem versão publicada")
    start = effective_from or timezone.localdate()
    metadata = {"adoptedFromTemplate": {"code": version.code, "versionNo": version.version_no}}
    created = []
    for key, value in sorted((version.content_json.get("configurations") or {}).items()):
        configuration = create_configuration(request, key, value, start, None, metadata)
        created.append({"configKey": key, "configurationId": str(configuration.id),
                        "versionNo": configuration.version_no, "status": configuration.status})
    market = None
    if version.content_json.get("marketProducts"):
        from apps.product.application.market_template_service import apply_market_templates

        market = apply_market_templates()
    return {
        "template": {"code": version.code, "versionNo": version.version_no, "name": version.name},
        "effectiveFrom": start.isoformat(),
        "createdDrafts": created,
        "marketProducts": market,
        "next": "Reveja e simule os rascunhos, submeta-os e peça a outra pessoa para os aprovar.",
    }
