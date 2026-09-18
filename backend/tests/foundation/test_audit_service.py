from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.tenant import TenantId


@dataclass
class FakeAuditRepository:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.fixture(autouse=True)
def _reset_actor_context():
    yield
    CurrentActorProvider.bind(None)


def test_record_requires_authenticated_actor():
    CurrentActorProvider.bind(None)
    service = AuditService(FakeAuditRepository())
    with pytest.raises(LookupError):
        service.record(action="quote.created", entity_type="Quote")


def test_record_forwards_actor_and_tenant():
    actor = Actor(
        actor_id="user-1",
        tenant_id=TenantId.parse("11111111-1111-1111-1111-111111111111"),
        roles=frozenset({Role.SUBSCRIBER}),
    )
    CurrentActorProvider.bind(actor)
    repository = FakeAuditRepository()
    service = AuditService(repository)

    service.record(
        action="quote.created",
        entity_type="Quote",
        entity_id="q-1",
        correlation_id="corr-1",
        metadata={"amount": 100, "token": "should-be-stripped"},
    )

    assert len(repository.calls) == 1
    call = repository.calls[0]
    assert call["actor"] is actor
    assert call["tenant_id"] == actor.tenant_id
    assert call["action"] == "quote.created"
    assert call["entity_id"] == "q-1"
    assert call["correlation_id"] == "corr-1"
    assert call["metadata"] == {"amount": 100}  # "token" key sanitised out


def test_record_sanitises_nested_credentials():
    actor = Actor(
        actor_id="user-1",
        tenant_id=TenantId.parse("11111111-1111-1111-1111-111111111111"),
        roles=frozenset({Role.SUBSCRIBER}),
    )
    CurrentActorProvider.bind(actor)
    repository = FakeAuditRepository()
    AuditService(repository).record(
        action="quote.failed",
        entity_type="Quote",
        metadata={"request": {"authorization": "Bearer leaked", "safe": "kept"}},
    )
    assert repository.calls[0]["metadata"] == {"request": {"safe": "kept"}}
