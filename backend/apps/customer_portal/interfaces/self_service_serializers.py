"""DTOs for the Fase 1 (ROADMAP_PORTAL_CLIENTE.md) authenticated
self-service endpoints, migrated to Policy in Fase 6
(DECISIONS_TAKEN.md#S09-POLICY-001). Not ART-006 — a new, small,
portal-owned contract, same as the Fase 0 pre-auth DTOs
(apps/customer_portal/interfaces/serializers.py).

`policy`/`product`/`plan` reuse the exact same serializers the staff API
already returns (`PolicySerializer`, `ProductSerializer`,
`PlanSerializer`) — per the roadmap's own Fase 1 task list: "reaproveitar
serializers já existentes, apenas restringindo o queryset ao proposer do
actor autenticado — nunca duplicar serializers". Whether these need a
thinner, customer-facing shape (hiding `rowVersion`/etc.) is an explicit
Fase 2 question in the roadmap, not decided here.
"""
from __future__ import annotations

from rest_framework import serializers


class CustomerPortalCoverageRequestSerializer(serializers.Serializer):
    policyNumber = serializers.CharField(max_length=100)
    # Optional: check a single dependent instead of every member on the
    # policy. Never trusted as a bare id — the view only accepts a
    # memberId that is actually a PolicyMember of the policyNumber above,
    # itself already resolved from the caller's own linked proposers.
    memberId = serializers.UUIDField(required=False, allow_null=True, default=None)
    date = serializers.DateField(required=False, allow_null=True, default=None)
    benefitCategory = serializers.CharField(required=False, allow_null=True, default=None, max_length=60)


class CustomerPortalCoverageResultSerializer(serializers.Serializer):
    memberId = serializers.UUIDField()
    covered = serializers.BooleanField()
    reasonCode = serializers.CharField()
    message = serializers.CharField()
    waitingPeriodEnds = serializers.DateField(allow_null=True)
