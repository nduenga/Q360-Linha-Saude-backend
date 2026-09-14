"""Controllers for the quote module. Every `security` scope and permission
combination below is copied from ART-006's `security` block per
`operationId`, cross-checked against
docs/artifacts/ART-006-openapi/ — plus DOC-001 s18 `quote:*` permissions
(all already defined in Sprint 1, see apps/foundation/domain/permissions.py).
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.pricing.interfaces.serializers import PricingResponseSerializer
from apps.quote.application import quote_service
from apps.quote.infrastructure.models import Quote
from apps.quote.interfaces.serializers import (
    QuoteCreateRequestSerializer,
    QuoteMemberRequestSerializer,
    QuoteMemberSerializer,
    QuotePriceRequestSerializer,
    QuoteSerializer,
    QuoteUpdateRequestSerializer,
)
from shared.pagination import Q360PageNumberPagination


class QuoteListCreateView(APIView):
    """ART-006 `/api/v1/quotes`: `listQuotes` (GET), `createQuote` (POST)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_CREATE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        queryset = Quote.objects.all().order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(QuoteSerializer(page, many=True).data)

    def post(self, request):
        body = QuoteCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        quote = quote_service.create_quote(
            proposer_id=data["proposerId"],
            product_version_id=data["productVersionId"],
            plan_id=data["planId"],
            effective_date=data["effectiveDate"],
        )
        return Response(QuoteSerializer(quote).data, status=201)


class QuoteDetailView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}`: `getQuote` (GET), `updateQuote` (PUT)."""

    def get_permissions(self):
        if self.request.method == "PUT":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(QuoteSerializer(quote).data)

    def put(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = quote_service.update_quote(quote=quote, effective_date=data["effectiveDate"], row_version=data["rowVersion"])
        return Response(QuoteSerializer(updated).data)


class QuoteMemberListCreateView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/members`: `addQuoteMember` (POST).
    `GET` (list) is a pragmatic V1 addition, not in ART-006 — `Quote` has
    no population field at all, see OPEN_DECISIONS.md#S04-LISTING-GAPS-001."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(quote.members.all().order_by("created_at"), request)
        return paginator.get_paginated_response(QuoteMemberSerializer(page, many=True).data)

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteMemberRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = quote_service.add_quote_member(
            quote=quote, member_id=body.validated_data["memberId"], correlation_id=get_correlation_id()
        )
        return Response(QuoteSerializer(updated).data)


class QuoteMemberDetailView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/members/{memberId}`: `removeQuoteMember` (DELETE)."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def delete(self, request, quote_id, member_id):
        quote = get_object_or_404(Quote, id=quote_id)
        quote_service.remove_quote_member(quote=quote, member_id=member_id)
        return Response(status=204)


class QuotePriceView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/price`: `priceQuote` (POST)."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CALCULATE)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuotePriceRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        pricing_run = quote_service.price_quote(
            quote=quote, recalculate=body.validated_data["recalculate"], correlation_id=get_correlation_id()
        )
        return Response(PricingResponseSerializer(pricing_run).data)
