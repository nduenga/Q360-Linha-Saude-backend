"""DTOs for the Fase 1 (ROADMAP_PORTAL_CLIENTE.md) authenticated
self-service endpoints. Not ART-006 — a new, small, portal-owned
contract, same as the Fase 0 pre-auth DTOs
(apps/customer_portal/interfaces/serializers.py).

`quote`/`product`/`productVersion`/`plan` reuse the exact same
serializers the staff API already returns (`QuoteSerializer`,
`ProductSerializer`, `ProductVersionSerializer`, `PlanSerializer`,
`PlanBenefitSerializer`) — per the roadmap's own Fase 1 task list:
"reaproveitar QuoteSerializer/ProductVersionSerializer já existentes,
apenas restringindo o queryset ao proposer do actor autenticado — nunca
duplicar serializers". Whether these need a thinner, customer-facing
shape (hiding `rowVersion`/`latestPricingRunId`/etc.) is an explicit
Fase 2 question in the roadmap, not decided here.
"""
from __future__ import annotations

from rest_framework import serializers


class CustomerPortalEligibilityRequestSerializer(serializers.Serializer):
    quoteNumber = serializers.CharField(max_length=100)
    # Optional: evaluate a single dependent instead of every member on the
    # policy. Never trusted as a bare id — the view only accepts a
    # memberId that is actually a QuoteMember of the quoteNumber above,
    # itself already resolved from the caller's own linked proposers.
    memberId = serializers.UUIDField(required=False, allow_null=True, default=None)


class CustomerPortalEligibilityResultSerializer(serializers.Serializer):
    memberId = serializers.UUIDField()
    relationshipCode = serializers.CharField(allow_null=True)
    decision = serializers.CharField()
    messages = serializers.ListField(child=serializers.JSONField())
