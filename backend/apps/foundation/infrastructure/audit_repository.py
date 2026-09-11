"""Django ORM adapter for AuditRepositoryPort.

Equivalent of DOC-004 s6.1's `JpaAuditRepositoryAdapter`, backed by the
Django ORM instead of JPA.
"""
from __future__ import annotations

from typing import Any

from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import AuditEvent


class DjangoAuditRepositoryAdapter:
    def record(
        self,
        *,
        tenant_id: TenantId,
        actor: Actor,
        action: str,
        entity_type: str,
        entity_id: str | None,
        correlation_id: str | None,
        trace_id: str | None,
        source: str | None,
        metadata: dict[str, Any],
    ) -> None:
        AuditEvent.objects.create(
            tenant_id=tenant_id.value,
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            source=source,
            metadata_json=metadata,
        )
