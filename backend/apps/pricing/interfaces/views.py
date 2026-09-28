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
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.pricing.application.pricing_engine import calculate_pricing, create_pricing_scenario, get_pricing_run
from apps.pricing.application.rating_table_service import (
    create_rating_table,
    delete_rating_table,
    update_rating_table,
)
from apps.pricing.infrastructure.models import PricingRun, RatingTable
from apps.pricing.interfaces.serializers import (
    PricingCalculateRequestSerializer,
    PricingExecutionSerializer,
    PricingExplanationSerializer,
    PricingResponseSerializer,
    PricingScenarioRequestSerializer,
    RatingTableRequestSerializer,
    RatingTableUpdateRequestSerializer,
    VersionedConfigHeaderSerializer,
)
from shared.pagination import Q360PageNumberPagination


@requires_idempotency
class RatingTableCreateView(APIView):
    """`GET` (list) is a pragmatic V1 addition, not in ART-006 — see
    OPEN_DECISIONS.md#S04-LISTING-GAPS-001/DECISIONS_TAKEN.md."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.ADMIN)(), require_permission(Permission.PRICING_CONFIG_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        queryset = RatingTable.objects.all().order_by("code", "-version_no")
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(VersionedConfigHeaderSerializer(page, many=True).data)

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


@requires_idempotency
class RatingTableDetailView(APIView):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6, pragmatic V1 addition, not
    in ART-006. `PATCH`/`DELETE` only work while `status=DRAFT` — see
    rating_table_service.update_rating_table/delete_rating_table."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]

    def patch(self, request, rating_table_id):
        rating_table = get_object_or_404(RatingTable, id=rating_table_id)
        body = RatingTableUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = update_rating_table(
            rating_table, name=data["name"], currency_code=data["currencyCode"], factor_rows=data["factors"]
        )
        return Response(VersionedConfigHeaderSerializer(updated).data)

    def delete(self, request, rating_table_id):
        rating_table = get_object_or_404(RatingTable, id=rating_table_id)
        delete_rating_table(rating_table)
        return Response(status=204)


@requires_idempotency
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


@requires_idempotency
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


class PricingExecutionListView(APIView):
    """
    GET /api/v1/pricing/runs

    Lista todas as tarifaçōes executadas.
    """

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        queryset = PricingRun.objects.all().order_by(
            "-created_at"
        )

        status = request.query_params.get("status")
        plan_id = request.query_params.get("planId")

        if status:
            queryset = queryset.filter(status=status)

        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)

        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
        )

        return paginator.get_paginated_response(
            PricingExecutionSerializer(
                page,
                many=True,
            ).data
        )


class PricingExecutionDetailView(APIView):
    """
    GET /api/v1/pricing/runs/{id}

    Devolve uma execução completa da tarifação.
    """

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, pricing_run_id):
        pricing_run = get_object_or_404(
            PricingRun,
            id=pricing_run_id,
        )

        return Response(
            PricingExecutionSerializer(
                pricing_run
            ).data
        )