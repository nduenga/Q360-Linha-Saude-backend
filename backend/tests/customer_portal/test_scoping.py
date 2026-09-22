"""apps.customer_portal.infrastructure.scoping.require_customer_proposer_ids
— fail-closed: never returns an implicit "no restriction" when the bound
actor isn't a CUSTOMER (ROADMAP_PORTAL_CLIENTE.md Fase 0's "second
security boundary").
"""
from __future__ import annotations

import pytest

from apps.customer_portal.infrastructure.scoping import require_customer_proposer_ids
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId

_TENANT = TenantId.parse("11111111-1111-1111-1111-111111111111")


@pytest.fixture(autouse=True)
def _reset_actor():
    yield
    CurrentActorProvider.bind(None)


def test_raises_when_no_actor_bound():
    CurrentActorProvider.bind(None)
    with pytest.raises(LookupError):
        require_customer_proposer_ids()


def test_raises_when_actor_is_staff_not_customer():
    CurrentActorProvider.bind(Actor(actor_id="staff-1", tenant_id=_TENANT, roles=frozenset(), actor_type="USER"))
    with pytest.raises(LookupError):
        require_customer_proposer_ids()


def test_returns_bound_proposer_ids_for_customer_actor():
    CurrentActorProvider.bind(
        Actor(
            actor_id="cust-1",
            tenant_id=_TENANT,
            roles=frozenset(),
            actor_type="CUSTOMER",
            customer_proposer_ids=frozenset({"p-1", "p-2"}),
        )
    )
    assert require_customer_proposer_ids() == frozenset({"p-1", "p-2"})
