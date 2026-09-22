"""The second security boundary ROADMAP_PORTAL_CLIENTE.md Fase 0 requires
for a `actor_type="CUSTOMER"` actor: tenant scoping
(`apps.foundation.infrastructure.tenant_scoping.TenantScopedManager`)
alone is not enough, because it does not stop one customer of a tenant
from seeing another customer's data within that same tenant — something
staff actors never needed (staff always saw the whole tenant). Fail-closed
the same way `CurrentTenantProvider.require()` is: raises rather than
silently returning an unscoped/empty result if called outside a bound
`CUSTOMER` actor context.

Fase 1 read endpoints (not yet built) must filter every Quote/QuoteMember/
etc. queryset by `proposer_id__in=require_customer_proposer_ids()` — never
trust a `proposerId` supplied by the request itself (ROADMAP_PORTAL_CLIENTE.md
Fase 1: "nunca aceitando esses IDs vindos do pedido do cliente").
"""
from __future__ import annotations

from apps.foundation.application.context import CurrentActorProvider


def require_customer_proposer_ids() -> frozenset[str]:
    actor = CurrentActorProvider.get()
    if actor is None or actor.actor_type != "CUSTOMER":
        raise LookupError("No authenticated customer-portal actor bound to the current context")
    return actor.customer_proposer_ids
