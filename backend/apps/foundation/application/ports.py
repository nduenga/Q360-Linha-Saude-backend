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


class EventPublisher(Protocol):
    """Port for the "publish" side of the Transactional Outbox.

    The default adapter is `ValidatingNoopPublisher` (never touches a real
    broker — the spec explicitly excludes connecting to RabbitMQ in V1).
    A real RabbitMQ/Kafka adapter can be plugged in later without changing
    any business-layer call sites. Implementation must raise `PublishError`
    if the envelope cannot be accepted.
    """

    def publish(self, envelope: dict[str, Any]) -> None: ...


class PublishError(Exception):
    """Raised by `EventPublisher.publish` when the envelope cannot be
    accepted (invalid shape, downstream broker unreachable, etc.). The
    dispatcher converts this into a FAILED transition with backoff."""
