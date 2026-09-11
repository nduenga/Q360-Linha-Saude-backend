"""Application ports (protocols) for the foundation module (DOC-004 s6.1).

Infrastructure adapters implement these; application/domain code never
imports Django ORM/JWT libraries directly (DOC-004 s3 dependency rule).
"""
from __future__ import annotations

from typing import Any, Protocol

from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId


class AuditRepositoryPort(Protocol):
    """DOC-004 s6.1 — AuditRepositoryPort."""

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
    ) -> None: ...
