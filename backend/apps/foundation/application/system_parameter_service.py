"""Parâmetros globais do sistema vistos pelo tenant: leitura com a
prioridade entre a camada geral do fornecedor e o tenant, alteração com
motivo/histórico/auditoria e rollback (R7). As definições estão em
`apps.foundation.domain.system_parameters`; a camada geral em
`platform_parameter_service`."""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.application import platform_parameter_service as platform
from apps.foundation.domain.system_parameters import (
    DEFINITIONS,
    LEGAL,
    LIMIT,
    InvalidSystemParameterError,
    StructuralParameterError,
    validate_value,
)
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.foundation.infrastructure.models import SystemParameter, SystemParameterRevision

_audit = AuditService(DjangoAuditRepositoryAdapter())


class UnknownSystemParameterError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


class SystemParameterConflictError(DomainProblem):
    http_status = 409
    problem_code = "VERSION-CONFLICT"


def _definition(code: str):
    definition = DEFINITIONS.get(code)
    if definition is None:
        raise UnknownSystemParameterError(f"Parâmetro de sistema '{code}' desconhecido")
    return definition


def _tenant_row(code: str):
    return SystemParameter.objects.filter(code=code).first()


def _resolve(code: str) -> tuple[Any, str, Any]:
    """(value, source, tenant row) — the priority between the levels:
    PLATFORM_MANDATORY → the platform's value always; PLATFORM_DEFAULT → the
    tenant's value while it is inside the platform's limits, otherwise the
    platform's value; with no platform version, the code default."""
    definition = _definition(code)
    version = platform.effective_version(code)
    platform_val = version.value_json if version is not None else definition.default
    platform_source = "PLATFORM" if version is not None else "CODE_DEFAULT"
    if not definition.tenant_editable:
        return platform_val, platform_source, None
    row = _tenant_row(code)
    if row is not None and platform.within_limits(row.value_json, platform.platform_limits(code)):
        return row.value_json, "TENANT", row
    return platform_val, platform_source, row


def get_value(code: str) -> Any:
    """Current value for the tenant bound to the context (see `_resolve`).
    Used by the modules that consume parameters."""
    return _resolve(code)[0]


def get_stored_value(code: str) -> Any:
    """The value someone explicitly set — the tenant (inside the limits) or
    the platform — or None when nobody did (so a caller can fall back to its
    own configuration, e.g. an env setting)."""
    value, source, _ = _resolve(code)
    return None if source == "CODE_DEFAULT" else value


def get_platform_version(code: str) -> int:
    """Version number of the platform value in effect (0 = code default);
    the pricing trace records it next to the legal taxes it applies."""
    version = platform.effective_version(code)
    return version.version_no if version is not None else 0


def describe(code: str) -> dict[str, Any]:
    definition = _definition(code)
    value, source, row = _resolve(code)
    version = platform.effective_version(code)
    platform_val = version.value_json if version is not None else definition.default
    lo, hi = platform.platform_limits(code) if definition.tenant_editable else (definition.minimum, definition.maximum)
    return {
        "code": code,
        "valueType": definition.value_type,
        "category": definition.category,
        "level": definition.level,
        "value": value,
        "source": source,
        "default": platform_val,
        "platformVersionNo": version.version_no if version is not None else 0,
        "isDefault": source != "TENANT",
        "tenantValueOutOfLimits": row is not None and source != "TENANT",
        "description": definition.description,
        "unit": definition.unit,
        "constraints": {"minimum": lo, "maximum": hi},
        "usedBy": definition.used_by,
        "editable": definition.tenant_editable,
        "rowVersion": row.row_version if row is not None else 0,
        "updatedBy": row.updated_by if row is not None else (version.decided_by if version is not None else None),
        "updatedAt": (
            row.updated_at.isoformat() if row is not None
            else (version.decided_at.isoformat() if version is not None and version.decided_at else None)
        ),
    }


def list_parameters(*, category: str | None = None) -> list[dict[str, Any]]:
    CurrentTenantProvider.require()
    rows = [describe(code) for code in DEFINITIONS]
    return [r for r in rows if category is None or r["category"] == category]


def _record_revision(*, code: str, action: str, value: Any, reason: str | None) -> SystemParameterRevision:
    tenant_id = CurrentTenantProvider.require().value
    actor = CurrentActorProvider.get()
    last = SystemParameterRevision.objects.filter(code=code).aggregate(m=Max("revision_no"))["m"] or 0
    return SystemParameterRevision.objects.create(
        tenant_id=tenant_id, code=code, revision_no=last + 1, action=action, value_json=value, reason=reason,
        changed_by=actor.actor_id if actor else "unknown",
    )


def set_value(*, code: str, value: Any, reason: str | None, row_version: int, action: str = "UPDATED") -> dict[str, Any]:
    definition = _definition(code)
    if not definition.tenant_editable:
        kind = {
            LEGAL: "um valor legal",
            LIMIT: "um teto que o fornecedor impõe a todas as seguradoras",
        }.get(definition.category, "um parâmetro estrutural (faz parte do motor de cálculo)")
        raise StructuralParameterError(
            f"'{code}' é {kind}, definido pelo fornecedor para todos os tenants: o tenant só o consulta"
        )
    reason = require_reason(reason)
    clean = validate_value(definition, value)
    limits = platform.platform_limits(code)
    if not platform.within_limits(clean, limits):
        raise InvalidSystemParameterError(
            f"{code} tem de estar entre {limits[0]} e {limits[1]} (limites definidos pelo fornecedor)"
        )
    tenant_id = CurrentTenantProvider.require().value
    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    before = describe(code)
    with transaction.atomic():
        row = SystemParameter.objects.select_for_update().filter(code=code).first()
        if row is None:
            if row_version != 0:
                raise SystemParameterConflictError(f"'{code}' ainda não tem valor guardado: a versão (rowVersion) tem de ser 0")
            SystemParameter.objects.create(tenant_id=tenant_id, code=code, value_json=clean, updated_by=actor_id)
        else:
            if row.row_version != row_version:
                raise SystemParameterConflictError(
                    f"A versão (rowVersion) {row_version} de '{code}' não coincide com a versão atual {row.row_version}"
                )
            SystemParameter.objects.filter(id=row.id).update(value_json=clean, updated_by=actor_id, row_version=row_version + 1)
        _record_revision(code=code, action=action, value=clean, reason=reason)
    after = describe(code)
    _audit.record(
        action="system_parameter.updated" if action == "UPDATED" else "system_parameter.rolled_back",
        entity_type="SystemParameter",
        entity_id=code,
        metadata=change_metadata(before={"value": before["value"]}, after={"value": after["value"]}, reason=reason),
    )
    return after


def list_revisions(*, code: str):
    _definition(code)
    return SystemParameterRevision.objects.filter(code=code).order_by("-revision_no")


def rollback(*, code: str, revision_no: int, reason: str | None) -> dict[str, Any]:
    reason = require_reason(reason)
    revision = SystemParameterRevision.objects.filter(code=code, revision_no=revision_no).first()
    if revision is None:
        raise UnknownSystemParameterError(f"'{code}' não tem a revisão {revision_no}")
    current = SystemParameter.objects.filter(code=code).first()
    return set_value(
        code=code,
        value=revision.value_json,
        reason=f"Rollback para a revisão {revision_no}: {reason}",
        row_version=current.row_version if current else 0,
        action=f"ROLLBACK_TO_{revision_no}",
    )

