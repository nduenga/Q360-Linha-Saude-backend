"""Transactional Outbox service (ART-007, Q360-S09).

Business code should never write directly to `outbox_event` — it must go
through `OutboxService.append`, which MUST be called inside the same
`transaction.atomic()` block that writes the actual state change. This is
what makes it "transactional": if the business transaction rolls back, the
pending outbox row is also rolled back (both inserts share the same DB
transaction), so a phantom event can never escape.

The envelope shape follows ART-007's `envelope` schema verbatim. The
"payload" argument to `append` is the INNER event payload (the business
fields specific to each event type); the outer envelope fields (eventId,
eventType, schemaVersion, occurredAt, tenantId, aggregateType, aggregateId,
correlationId, causationId, producer, payload) are assembled here and
persisted as `payload_json` on the `OutboxEvent` row.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from django.utils import timezone

from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.ports import PublishError
from apps.foundation.infrastructure.models import OutboxEvent
from apps.foundation.interfaces.middleware import get_correlation_id

PRODUCER_NAME = "q360-core"
_SCHEMA_VERSION_DEFAULT = 1

_REQUIRED_ENVELOPE_FIELDS = {
    "eventId",
    "eventType",
    "schemaVersion",
    "occurredAt",
    "tenantId",
    "aggregateType",
    "aggregateId",
    "correlationId",
    "causationId",
    "producer",
    "payload",
}

_FORBIDDEN_PAYLOAD_KEYS_CASE_INSENSITIVE = {
    "password",
    "secret",
    "authorization",
    "access_token",
    "refresh_token",
    "jwt",
    "api_key",
    "token",
}


class ValidatingNoopPublisher:
    """Default EventPublisher adapter (V1).

    Never touches a real message broker. Per spec (Assumptions section),
    "successful publication" in V1 means:
      1. every required envelope field is present (non-empty where relevant)
      2. json.dumps → json.loads round-trips without loss
      3. no obviously-forbidden keys (tokens/passwords) appear anywhere in
         the payload tree (case-insensitive)
    """

    def publish(self, envelope: dict[str, Any]) -> None:
        missing = _REQUIRED_ENVELOPE_FIELDS - set(envelope.keys())
        if missing:
            raise PublishError(f"Faltam campos obrigatórios no envelope: {sorted(missing)}")
        for field in ("eventType", "tenantId", "aggregateType", "aggregateId"):
            value = envelope.get(field)
            if value is None or value == "":
                raise PublishError(f"O campo {field} do envelope não pode estar vazio")

        try:
            round_trip = json.loads(json.dumps(envelope, default=str))
        except (TypeError, ValueError) as exc:
            raise PublishError(f"O envelope não é serializável em JSON: {exc}") from exc

        forbidden_found = _scan_forbidden_keys(round_trip)
        if forbidden_found:
            raise PublishError(f"O conteúdo (payload) tem chaves proibidas: {sorted(forbidden_found)}")


def _scan_forbidden_keys(node: Any, _found: set[str] | None = None) -> set[str]:
    found: set[str] = _found if _found is not None else set()
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.lower() in _FORBIDDEN_PAYLOAD_KEYS_CASE_INSENSITIVE:
                found.add(k)
            _scan_forbidden_keys(v, found)
    elif isinstance(node, list):
        for item in node:
            _scan_forbidden_keys(item, found)
    return found


class OutboxService:
    def __init__(self) -> None:
        self._publisher: Any = None

    def set_publisher(self, publisher: Any) -> None:
        self._publisher = publisher

    def get_publisher(self) -> Any:
        if self._publisher is None:
            self._publisher = ValidatingNoopPublisher()
        return self._publisher

    def append(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        schema_version: int = _SCHEMA_VERSION_DEFAULT,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> OutboxEvent:
        """Append a pending outbox event.

        MUST be called inside `transaction.atomic()` that also writes the
        corresponding state change — the whole point of the outbox pattern
        is that both writes share a single DB transaction.
        """
        tenant_id = CurrentTenantProvider.require()
        effective_correlation_id = (
            correlation_id if correlation_id is not None else get_correlation_id()
        )
        event_id = uuid.uuid4()
        envelope = {
            "eventId": str(event_id),
            "eventType": event_type,
            "schemaVersion": schema_version,
            "occurredAt": timezone.now().isoformat(),
            "tenantId": str(tenant_id.value),
            "aggregateType": aggregate_type,
            "aggregateId": str(aggregate_id),
            "correlationId": effective_correlation_id or "",
            "causationId": causation_id or "",
            "producer": PRODUCER_NAME,
            "payload": payload,
        }

        return OutboxEvent.objects.create(
            tenant_id=tenant_id.value,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            event_type=event_type,
            schema_version=schema_version,
            payload_json=envelope,
            correlation_id=effective_correlation_id,
            causation_id=causation_id,
            status="PENDING",
        )


_outbox_service = OutboxService()


def get_outbox_service() -> OutboxService:
    return _outbox_service


def _backoff_next_attempt(attempts: int) -> Any:
    """Short exponential backoff schedule per spec: 10s, 30s, 2m, 10m, 30m."""
    from datetime import timedelta

    schedule_seconds = [10, 30, 120, 600, 1800]
    idx = max(0, min(attempts, len(schedule_seconds) - 1))
    return timezone.now() + timedelta(seconds=schedule_seconds[idx])
