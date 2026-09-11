from __future__ import annotations

import pytest

from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.tenant import TenantId


def _actor() -> Actor:
    return Actor(
        actor_id="user-1",
        tenant_id=TenantId.parse("11111111-1111-1111-1111-111111111111"),
        roles=frozenset({Role.SUBSCRIBER}),
    )


def test_current_tenant_requires_bound_actor():
    CurrentActorProvider.bind(None)
    with pytest.raises(LookupError):
        CurrentTenantProvider.require()


def test_current_tenant_resolves_from_bound_actor():
    actor = _actor()
    token = CurrentActorProvider.bind(actor)
    try:
        assert CurrentActorProvider.get() is actor
        assert CurrentTenantProvider.require() == actor.tenant_id
    finally:
        CurrentActorProvider.reset(token)
        assert CurrentActorProvider.get() is None
