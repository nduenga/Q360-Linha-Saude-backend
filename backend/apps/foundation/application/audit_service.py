"""AuditService (DOC-004 s6.1/6.2, Q360-S1-05).

Records auditable operations against the currently bound actor/tenant.
Never persists secrets, tokens or raw clinical payloads — DOC-004 s6.2:
"Audit não deve guardar token, password, secret, questionário clínico
integral ou payload bruto desnecessário." Callers must still avoid putting
such data in `metadata`; `_FORBIDDEN_METADATA_KEYS` is a defensive net, not
a substitute for that discipline.

DOC-001 s19 lists "Resultado" (outcome) and, for decisions, "Motivo"
(reason) as mandatory audit elements — but ART-005's `q360.audit_event`
(authoritative physical schema, DOC-004 s2) has no dedicated `result` or
`reason` column, only `metadata_json`. Since the schema cannot be altered
outside a Change Request against ART-005 (DOC-000 s12), callers that record
a decision or an outcome-bearing action MUST put `result` (e.g.
"SUCCESS"/"FAILURE"/"APPROVED"/"REJECTED") and, where DOC-001 requires a
reason, `reason` inside `metadata`. This is a convention, not an enforced
parameter, because `AuditService.record` is generic across all future
modules — S2+ call sites are responsible for including them where DOC-001
s19 requires it.
"""
from __future__ import annotations

from typing import Any

from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.ports import AuditRepositoryPort
from apps.foundation.interfaces.middleware import get_correlation_id

_FORBIDDEN_METADATA_KEYS = {
    "token",
    "password",
    "secret",
    "authorization",
    "access_token",
    "refresh_token",
    "jwt",
    "api_key",
}


class AuditService:
    def __init__(self, repository: AuditRepositoryPort) -> None:
        self._repository = repository

    def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        actor = CurrentActorProvider.get()
        if actor is None:
            raise LookupError("O registo de auditoria exige um utilizador autenticado")
        tenant_id = CurrentTenantProvider.require()
        effective_correlation_id = correlation_id if correlation_id is not None else get_correlation_id()
        effective_metadata: dict[str, Any] = dict(metadata or {})
        self._repository.record(
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=effective_correlation_id,
            trace_id=trace_id,
            source=source,
            metadata=_sanitise(effective_metadata),
        )


def _sanitise(metadata: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove credentials from nested audit metadata too."""
    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if not isinstance(key, str) or key.lower() not in _FORBIDDEN_METADATA_KEYS
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(metadata)
