"""Parâmetros globais do sistema: leitura com valor por omissão, alteração
com motivo/histórico/auditoria e rollback (R7). As definições estão em
`apps.foundation.domain.system_parameters`."""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.domain.system_parameters import (
    DEFINITIONS,
    OPERATIONAL,
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
        raise UnknownSystemParameterError(f"Unknown system parameter '{code}'")
    return definition


def get_value(code: str) -> Any:
    """Current value for the tenant bound to the context (default when the
    GTE never changed it). Used by the modules that consume parameters."""
    definition = _definition(code)
    row = SystemParameter.objects.filter(code=code).first()
    return row.value_json if row is not None else definition.default


def get_stored_value(code: str) -> Any:
    """The value the GTE explicitly set, or None when it never did (so a
    caller can fall back to its own configuration, e.g. an env setting)."""
    _definition(code)
    row = SystemParameter.objects.filter(code=code).first()
    return row.value_json if row is not None else None


def describe(code: str) -> dict[str, Any]:
    definition = _definition(code)
    row = SystemParameter.objects.filter(code=code).first()
    return {
        "code": code,
        "valueType": definition.value_type,
        "category": definition.category,
        "value": row.value_json if row is not None else definition.default,
        "default": definition.default,
        "isDefault": row is None,
        "description": definition.description,
        "unit": definition.unit,
        "constraints": definition.constraints(),
        "usedBy": definition.used_by,
        "editable": definition.category == OPERATIONAL,
        "rowVersion": row.row_version if row is not None else 0,
        "updatedBy": row.updated_by if row is not None else None,
        "updatedAt": row.updated_at.isoformat() if row is not None else None,
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
    if definition.category != OPERATIONAL:
        raise StructuralParameterError(
            f"'{code}' is a structural parameter (part of the calculation engine): changing it needs a system evolution"
        )
    reason = require_reason(reason)
    clean = validate_value(definition, value)
    tenant_id = CurrentTenantProvider.require().value
    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    before = describe(code)
    with transaction.atomic():
        row = SystemParameter.objects.select_for_update().filter(code=code).first()
        if row is None:
            if row_version != 0:
                raise SystemParameterConflictError(f"'{code}' has no stored value yet: rowVersion must be 0")
            SystemParameter.objects.create(tenant_id=tenant_id, code=code, value_json=clean, updated_by=actor_id)
        else:
            if row.row_version != row_version:
                raise SystemParameterConflictError(
                    f"'{code}' rowVersion {row_version} does not match the current version {row.row_version}"
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
        raise UnknownSystemParameterError(f"'{code}' has no revision {revision_no}")
    current = SystemParameter.objects.filter(code=code).first()
    return set_value(
        code=code,
        value=revision.value_json,
        reason=f"Rollback para a revisão {revision_no}: {reason}",
        row_version=current.row_version if current else 0,
        action=f"ROLLBACK_TO_{revision_no}",
    )

