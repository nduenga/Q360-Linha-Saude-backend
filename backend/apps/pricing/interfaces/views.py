"""ART-006 `/api/v1/rating-tables`: `createRatingTable` (POST), security ->
oauth2: [q360.admin]. Gated additionally by DOC-001 s18
`pricing-config:manage` — rating tables are unambiguously pricing
configuration (unlike the shared rule-version endpoint, which spans
domains and is scope-only, see apps/product/interfaces/views.py
ConfigurationPublishView).
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.pricing.application.pricing_engine import calculate_pricing, create_pricing_scenario, get_pricing_run
from apps.pricing.application.rating_table_service import create_rating_table
from apps.pricing.infrastructure.models import PricingRun
from apps.pricing.interfaces.serializers import (
    PricingCalculateRequestSerializer,
    PricingExplanationSerializer,
    PricingResponseSerializer,
    PricingScenarioRequestSerializer,
    RatingTableRequestSerializer,
    VersionedConfigHeaderSerializer,
)


class RatingTableCreateView(APIView):
    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]

    def post(self, request):
        body = RatingTableRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        rating_table = create_rating_table(
            code=data["code"],
            name=data["name"],
            effective_from=data["effectiveFrom"],
            effective_to=data["effectiveTo"],
            currency_code=data["currencyCode"],
            factor_rows=data["factors"],
        )
        return Response(VersionedConfigHeaderSerializer(rating_table).data, status=201)


class PricingCalculateView(APIView):
    """ART-006 `/api/v1/pricing/calculate` (Q360-S4-02), security ->
    oauth2: [q360.write]. Gated additionally by DOC-001 s18
    `quote:calculate` — the same permission DOC-001 grants the Subscritor
    persona for "Calcular prémio determinístico"."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CALCULATE)]

    def post(self, request):
        body = PricingCalculateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        pricing_run = calculate_pricing(
            product_version_id=data["productVersionId"],
            plan_id=data["planId"],
            effective_date=data["effectiveDate"],
            member_ids=data["memberIds"],
            context=data["context"],
            correlation_id=get_correlation_id(),
        )
        return Response(PricingResponseSerializer(pricing_run).data, status=200)


class PricingExplanationView(APIView):
    """ART-006 `/api/v1/pricing/{pricingRunId}/explanation` (Q360-S4-04),
    security -> oauth2: [q360.read]. No DOC-001 permission cleanly maps to
    this read (actor is "Subscritor/Auditor", spanning two personas with
    different DOC-001 grants) — scope-only, same posture as the eligibility
    and client domains where no matrix cell fits."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, pricing_run_id):
        pricing_run = get_object_or_404(PricingRun, id=pricing_run_id)
        return Response(PricingExplanationSerializer(pricing_run).data, status=200)


class PricingScenarioView(APIView):
    """ART-006 `/api/v1/pricing/scenarios` (Q360-S5-02), security ->
    oauth2: [q360.write]. Gated by DOC-001 s18 `quote:calculate`, same as
    `PricingCalculateView` — a scenario is a variant calculation."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CALCULATE)]

    def post(self, request):
        body = PricingScenarioRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        base_pricing_run = get_object_or_404(PricingRun, id=data["basePricingRunId"])
        scenario = create_pricing_scenario(
            base_pricing_run=base_pricing_run,
            name=data["name"],
            overrides=data["overrides"],
            correlation_id=get_correlation_id(),
        )
        return Response(PricingResponseSerializer(scenario.result_pricing_run).data, status=201)
