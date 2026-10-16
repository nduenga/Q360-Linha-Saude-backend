"""Camada de configuração geral do fornecedor (contas da plataforma).

Cada parâmetro de `apps.foundation.domain.system_parameters` tem um nível:
  - PLATFORM_MANDATORY (estruturais e legais): o valor em vigor é o da
    camada geral; o tenant só consulta.
  - PLATFORM_DEFAULT (operacionais): a camada geral dá o valor por omissão e
    os limites; o valor do tenant prevalece enquanto estiver dentro deles.

Alterações: uma conta da plataforma propõe uma versão (com motivo e
vigência opcional), outra aprova ou rejeita. A versão em vigor é a PUBLISHED
de maior número cuja vigência já começou; sem nenhuma, vale o valor por
omissão do código. Reverter cria uma versão nova (também sujeita a
aprovação) com o valor de uma versão publicada anterior.

Este módulo não depende do tenant em contexto: serve a API `/platform/…` e
a leitura feita pelos tenants e pelo motor."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.foundation.application.change_audit import require_reason
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.domain.system_parameters import (
    DEFINITIONS,
    LEGAL,
    PLATFORM_DEFAULT,
    InvalidSystemParameterError,
    ParameterDefinition,
    validate_limits,
    validate_platform_value,
    validate_value,
)
from apps.foundation.infrastructure.models import PlatformParameterVersion, SystemParameter


class UnknownPlatformParameterError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


class PlatformParameterStateError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


class PlatformFourEyesError(DomainProblem):
    http_status = 403
    problem_code = "SEC-403"


def definition(code: str) -> ParameterDefinition:
    found = DEFINITIONS.get(code)
    if found is None:
        raise UnknownPlatformParameterError(f"Parâmetro '{code}' desconhecido")
    return found


def effective_version(code: str, *, at: datetime.datetime | None = None) -> PlatformParameterVersion | None:
    moment = at or timezone.now()
    return (
        PlatformParameterVersion.objects.filter(
            code=code, status=PlatformParameterVersion.PUBLISHED, effective_from__lte=moment
        )
        .order_by("-version_no")
        .first()
    )


def snapshot() -> dict[str, int]:
    """{code: version in effect} for the parameters the platform changed —
    part of a quote's pricing fingerprint, so a new platform version (e.g. a
    new legal tax rate) makes the last calculation stale."""
    now = timezone.now()
    result: dict[str, int] = {}
    for code, version_no in (
        PlatformParameterVersion.objects.filter(status=PlatformParameterVersion.PUBLISHED, effective_from__lte=now)
        .order_by("code", "version_no")
        .values_list("code", "version_no")
    ):
        result[code] = version_no
    return result


def platform_value(code: str) -> Any:
    version = effective_version(code)
    return version.value_json if version is not None else definition(code).default


def platform_limits(code: str) -> tuple[Any, Any]:
    """Limits tenants must respect (PLATFORM_DEFAULT): the platform's when it
    narrowed them, otherwise the definition's hard limits."""
    d = definition(code)
    version = effective_version(code)
    lo = version.minimum_json if version is not None and version.minimum_json is not None else d.minimum
    hi = version.maximum_json if version is not None and version.maximum_json is not None else d.maximum
    return lo, hi


def within_limits(value: Any, limits: tuple[Any, Any]) -> bool:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, str)):
        return True
    try:
        number = Decimal(str(value))
    except ArithmeticError:
        return True
    lo, hi = limits
    return (lo is None or number >= Decimal(str(lo))) and (hi is None or number <= Decimal(str(hi)))


def version_payload(version: PlatformParameterVersion, *, in_effect_no: int | None = None) -> dict[str, Any]:
    return {
        "code": version.code,
        "versionNo": version.version_no,
        "status": version.status,
        "action": version.action,
        "value": version.value_json,
        "minimum": version.minimum_json,
        "maximum": version.maximum_json,
        "effectiveFrom": version.effective_from.isoformat() if version.effective_from else None,
        "inEffect": in_effect_no is not None and version.version_no == in_effect_no,
        "reason": version.reason,
        "legalReference": version.legal_reference,
        "sourceUrl": version.source_url,
        "createdBy": version.created_by,
        "createdAt": version.created_at.isoformat() if version.created_at else None,
        "decidedBy": version.decided_by,
        "decidedAt": version.decided_at.isoformat() if version.decided_at else None,
        "decisionNote": version.decision_note,
    }


def describe(code: str) -> dict[str, Any]:
    d = definition(code)
    version = effective_version(code)
    lo, hi = platform_limits(code)
    pending = PlatformParameterVersion.objects.filter(code=code, status=PlatformParameterVersion.PENDING_APPROVAL)
    payload: dict[str, Any] = {
        "code": code,
        "valueType": d.value_type,
        "category": d.category,
        "level": d.level,
        "value": version.value_json if version is not None else d.default,
        "codeDefault": d.default,
        "isCodeDefault": version is None,
        "versionNo": version.version_no if version is not None else 0,
        "effectiveFrom": version.effective_from.isoformat() if version is not None and version.effective_from else None,
        "legalReference": version.legal_reference if version is not None else None,
        "sourceUrl": version.source_url if version is not None else None,
        "requiresLegalReference": d.category == LEGAL,
        "description": d.description,
        "unit": d.unit,
        "usedBy": d.used_by,
        "hardLimits": d.constraints(),
        "tenantLimits": {"minimum": lo, "maximum": hi} if d.level == PLATFORM_DEFAULT else None,
        "allowedValues": list(d.allowed_values) if d.allowed_values is not None else None,
        "tenantEditable": d.tenant_editable,
        "pendingVersions": [version_payload(p) for p in pending.order_by("version_no")],
    }
    if d.level == PLATFORM_DEFAULT:
        payload["tenantOverrides"] = _tenant_override_summary(code, (lo, hi))
    return payload


def _tenant_override_summary(code: str, limits: tuple[Any, Any]) -> dict[str, int]:
    values = list(SystemParameter.all_tenants.filter(code=code).values_list("value_json", flat=True))
    return {"count": len(values), "outOfLimits": sum(1 for v in values if not within_limits(v, limits))}


def list_parameters(*, level: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    rows = [describe(code) for code in DEFINITIONS]
    return [r for r in rows if (level is None or r["level"] == level) and (category is None or r["category"] == category)]


def list_versions(code: str) -> list[dict[str, Any]]:
    definition(code)
    current = effective_version(code)
    in_effect_no = current.version_no if current is not None else None
    return [
        version_payload(v, in_effect_no=in_effect_no)
        for v in PlatformParameterVersion.objects.filter(code=code).order_by("-version_no")
    ]


def _clean_proposal(d: ParameterDefinition, value: Any, minimum: Any, maximum: Any) -> tuple[Any, Any, Any]:
    if d.level == PLATFORM_DEFAULT:
        lo, hi = validate_limits(d, minimum, maximum)
        clean = validate_value(d, value) if value is not None else None
        if clean is not None and not within_limits(clean, (lo, hi)):
            raise InvalidSystemParameterError(f"{d.code}: o valor por omissão tem de respeitar os limites propostos")
        # Guarda só os limites que o fornecedor de facto estreitou.
        return clean, (lo if minimum is not None else None), (hi if maximum is not None else None)
    if minimum is not None or maximum is not None:
        raise InvalidSystemParameterError(f"{d.code} é obrigatório para todos os tenants: não aceita limites")
    return validate_platform_value(d, value), None, None


def propose(
    *,
    code: str,
    value: Any,
    reason: str | None,
    actor_id: str,
    minimum: Any = None,
    maximum: Any = None,
    effective_from: datetime.datetime | None = None,
    action: str = "CREATED",
    legal_reference: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    d = definition(code)
    reason = require_reason(reason)
    legal_reference = (legal_reference or "").strip() or None
    source_url = (source_url or "").strip() or None
    if d.category == LEGAL and legal_reference is None:
        raise InvalidSystemParameterError(
            f"{code} é um valor legal: indique a fonte ('legalReference'), por exemplo o diploma e o artigo"
        )
    if source_url is not None and not source_url.startswith(("https://", "http://")):
        raise InvalidSystemParameterError("A ligação da fonte ('sourceUrl') tem de começar por https://")
    clean, lo, hi = _clean_proposal(d, value, minimum, maximum)
    if clean is None:
        raise InvalidSystemParameterError(f"{code}: indique o valor ('value')")
    if effective_from is not None and effective_from < timezone.now() - datetime.timedelta(minutes=1):
        raise InvalidSystemParameterError("A vigência ('effectiveFrom') não pode estar no passado")
    with transaction.atomic():
        # Serializa as propostas do mesmo código (número de versão e "uma pendente de cada vez").
        list(PlatformParameterVersion.objects.select_for_update().filter(code=code).values_list("id", flat=True))
        if PlatformParameterVersion.objects.filter(code=code, status=PlatformParameterVersion.PENDING_APPROVAL).exists():
            raise PlatformParameterStateError(
                f"'{code}' já tem uma versão à espera de aprovação: aprove-a ou rejeite-a primeiro"
            )
        last = PlatformParameterVersion.objects.filter(code=code).aggregate(m=Max("version_no"))["m"] or 0
        version = PlatformParameterVersion.objects.create(
            code=code, version_no=last + 1, action=action, value_json=clean, minimum_json=lo, maximum_json=hi,
            effective_from=effective_from, reason=reason, created_by=actor_id,
            legal_reference=legal_reference, source_url=source_url,
        )
    return version_payload(version)


def _pending(code: str, version_no: int) -> PlatformParameterVersion:
    definition(code)
    version = PlatformParameterVersion.objects.select_for_update().filter(code=code, version_no=version_no).first()
    if version is None:
        raise UnknownPlatformParameterError(f"'{code}' não tem a versão {version_no}")
    if version.status != PlatformParameterVersion.PENDING_APPROVAL:
        raise PlatformParameterStateError(f"A versão {version_no} de '{code}' já foi decidida ({version.status})")
    return version


def approve(*, code: str, version_no: int, actor_id: str, note: str | None = None) -> dict[str, Any]:
    with transaction.atomic():
        version = _pending(code, version_no)
        if version.created_by == actor_id:
            raise PlatformFourEyesError("Quem propôs a versão não a pode aprovar: tem de ser outra conta da plataforma")
        now = timezone.now()
        version.status = PlatformParameterVersion.PUBLISHED
        version.decided_by = actor_id
        version.decided_at = now
        version.decision_note = (note or "").strip() or None
        if version.effective_from is None or version.effective_from < now:
            version.effective_from = now
        version.save(update_fields=["status", "decided_by", "decided_at", "decision_note", "effective_from"])
    return version_payload(version)


def reject(*, code: str, version_no: int, actor_id: str, note: str | None) -> dict[str, Any]:
    note = require_reason(note)
    with transaction.atomic():
        version = _pending(code, version_no)
        version.status = PlatformParameterVersion.REJECTED
        version.decided_by = actor_id if actor_id != version.created_by else None
        version.decided_at = timezone.now()
        version.decision_note = note
        version.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    return version_payload(version)


def rollback(*, code: str, version_no: int, reason: str | None, actor_id: str) -> dict[str, Any]:
    reason = require_reason(reason)
    target = PlatformParameterVersion.objects.filter(
        code=code, version_no=version_no, status=PlatformParameterVersion.PUBLISHED
    ).first()
    if target is None:
        raise UnknownPlatformParameterError(f"'{code}' não tem a versão publicada {version_no}")
    return propose(
        code=code, value=target.value_json, minimum=target.minimum_json, maximum=target.maximum_json,
        reason=f"Reverter para a versão {version_no}: {reason}", actor_id=actor_id, action=f"ROLLBACK_TO_{version_no}",
        legal_reference=target.legal_reference, source_url=target.source_url,
    )
