"""Q360-S9-02 Transactional Outbox acceptance criteria (AC-4 in
.trae/specs/s09-s11-restantes/spec.md): OutboxService.append writes in the
same PostgreSQL transaction as the business change (so a rollback also
rolls back the outbox row), and `dispatch_outbox` marks valid envelopes
PUBLISHED and applies the documented backoff schedule (10s/30s/2m/10m/30m,
FAILED after 5 attempts) for invalid ones, without ever storing raw
payload content in `last_error_safe`.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.core.management import call_command
from django.db import transaction

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.application.ports import PublishError
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import OutboxEvent


@pytest.fixture(autouse=True)
def _bind_actor(tenant):
    actor = Actor(actor_id="outbox-tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    yield actor
    CurrentActorProvider.reset(token)


@pytest.mark.django_db
def test_append_persists_envelope_matching_art_007_shape(tenant):
    service = get_outbox_service()
    aggregate_id = str(uuid.uuid4())

    event = service.append(
        aggregate_type="QUOTE",
        aggregate_id=aggregate_id,
        event_type="QUOTE.CREATED",
        payload={"quoteId": aggregate_id, "status": "DRAFT"},
        correlation_id="corr-1",
    )

    row = OutboxEvent.objects.get(id=event.id)
    assert row.status == "PENDING"
    assert row.tenant_id == tenant.id
    envelope = row.payload_json
    for field in (
        "eventId", "eventType", "schemaVersion", "occurredAt", "tenantId",
        "aggregateType", "aggregateId", "correlationId", "causationId", "producer", "payload",
    ):
        assert field in envelope, field
    assert envelope["eventType"] == "QUOTE.CREATED"
    assert envelope["producer"] == "q360-core"
    assert envelope["payload"] == {"quoteId": aggregate_id, "status": "DRAFT"}


@pytest.mark.django_db
def test_rollback_also_rolls_outbox(tenant):
    service = get_outbox_service()
    aggregate_id = str(uuid.uuid4())

    class _Boom(Exception):
        pass

    with pytest.raises(_Boom):
        with transaction.atomic():
            service.append(
                aggregate_type="QUOTE",
                aggregate_id=aggregate_id,
                event_type="QUOTE.CREATED",
                payload={"quoteId": aggregate_id},
            )
            raise _Boom("simulated business-transaction failure")

    assert not OutboxEvent.objects.filter(aggregate_id=aggregate_id).exists()


@pytest.mark.django_db
def test_dispatch_marks_published(tenant):
    service = get_outbox_service()
    aggregate_id = str(uuid.uuid4())
    event = service.append(
        aggregate_type="QUOTE",
        aggregate_id=aggregate_id,
        event_type="QUOTE.SUBMITTED",
        payload={"quoteId": aggregate_id},
    )

    call_command("dispatch_outbox", "--once")

    row = OutboxEvent.objects.get(id=event.id)
    assert row.status == "PUBLISHED"
    assert row.published_at is not None
    assert row.attempts == 1


class _AlwaysFailsPublisher:
    def publish(self, envelope: dict[str, Any]) -> None:
        raise PublishError("simulated downstream failure: secret=should-never-be-stored token=abc123")


@pytest.mark.django_db
def test_dispatch_backoff_and_fail_after_five_attempts(tenant):
    service = get_outbox_service()
    service.set_publisher(_AlwaysFailsPublisher())
    try:
        aggregate_id = str(uuid.uuid4())
        event = service.append(
            aggregate_type="QUOTE",
            aggregate_id=aggregate_id,
            event_type="QUOTE.SUBMITTED",
            payload={"quoteId": aggregate_id},
        )

        for _pass in range(5):
            OutboxEvent.objects.filter(id=event.id).update(next_attempt_at=None)
            call_command("dispatch_outbox", "--once")

        row = OutboxEvent.objects.get(id=event.id)
        assert row.attempts == 5
        assert row.status == "FAILED"
        assert row.last_error_safe
        assert "secret=" not in row.last_error_safe
        assert "token=" not in row.last_error_safe
        assert "[redacted]" in row.last_error_safe
    finally:
        service.set_publisher(None)


@pytest.mark.django_db
def test_dispatch_backoff_schedule_before_exhaustion(tenant):
    service = get_outbox_service()
    service.set_publisher(_AlwaysFailsPublisher())
    try:
        aggregate_id = str(uuid.uuid4())
        event = service.append(
            aggregate_type="QUOTE",
            aggregate_id=aggregate_id,
            event_type="QUOTE.SUBMITTED",
            payload={"quoteId": aggregate_id},
        )

        call_command("dispatch_outbox", "--once")

        row = OutboxEvent.objects.get(id=event.id)
        assert row.attempts == 1
        assert row.status == "FAILED"
        assert row.next_attempt_at is not None
    finally:
        service.set_publisher(None)
