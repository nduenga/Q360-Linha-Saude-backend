"""Controllers for the quote module. Every `security` scope and permission
combination below is copied from ART-006's `security` block per
`operationId`, cross-checked against
docs/artifacts/ART-006-openapi/ — plus DOC-001 s18 `quote:*` permissions
(all already defined in Sprint 1, see apps/foundation/domain/permissions.py).
"""
from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application.permission_evaluator import PermissionEvaluator
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.pricing.interfaces.serializers import PricingResponseSerializer
from apps.quote.application import document_service, quote_service
from apps.quote.domain.enums import QuoteDecisionType
from apps.quote.infrastructure.models import DocumentTemplateVersion, Quote, ReviewTask
from apps.quote.interfaces.serializers import (
    CancelQuoteRequestSerializer,
    DecisionRequestSerializer,
    DocumentSerializer,
    DocumentTemplateCreateRequestSerializer,
    DocumentTemplateHeaderSerializer,
    QuoteCreateRequestSerializer,
    QuoteMemberRequestSerializer,
    QuoteMemberSerializer,
    QuotePriceRequestSerializer,
    QuoteSerializer,
    QuoteSubmitRequestSerializer,
    QuoteUpdateRequestSerializer,
    ReviewTaskSerializer,
    StateHistoryItemSerializer,
)
from shared.pagination import Q360PageNumberPagination

_DECISION_PERMISSION = {
    QuoteDecisionType.APPROVE.value: Permission.QUOTE_APPROVE,
    QuoteDecisionType.REJECT.value: Permission.QUOTE_REJECT,
    QuoteDecisionType.RETURN.value: Permission.QUOTE_REVIEW,
}


@requires_idempotency
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


@requires_idempotency
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


@requires_idempotency
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


@requires_idempotency
class QuoteMemberDetailView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/members/{memberId}`: `removeQuoteMember` (DELETE)."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def delete(self, request, quote_id, member_id):
        quote = get_object_or_404(Quote, id=quote_id)
        quote_service.remove_quote_member(quote=quote, member_id=member_id)
        return Response(status=204)


@requires_idempotency
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


@requires_idempotency
class QuoteSubmitView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/submit`: `submitQuote` (POST)."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_SUBMIT)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteSubmitRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = quote_service.submit_quote(
            quote=quote, row_version=body.validated_data["rowVersion"], correlation_id=get_correlation_id()
        )
        return Response(QuoteSerializer(updated).data)


class QuoteReviewView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/review`: `getQuoteReview` (GET)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        review_task = quote_service.get_active_review_task(quote=quote)
        if review_task is None:
            raise Http404
        return Response(ReviewTaskSerializer(review_task).data)


@requires_idempotency
class QuoteDecisionView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/decision`: `decideQuote` (POST) —
    handles APPROVE/REJECT/RETURN through one endpoint (`DecisionRequest`),
    gated by scope `q360.approve` uniformly and by a DOC-001 s18 permission
    that varies per decision (quote:approve/quote:reject/quote:review —
    see Commands & Authority sheet, ART-009)."""

    permission_classes = [require_scope(Scope.APPROVE)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = DecisionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        actor = getattr(getattr(request, "user", None), "actor", None)
        required_permission = _DECISION_PERMISSION[data["decision"]]
        if not PermissionEvaluator.is_authorised(actor, required_permission):
            raise PermissionDenied(f"Actor lacks {required_permission.value} for decision {data['decision']}")

        updated = quote_service.decide_quote(
            quote=quote,
            decision=data["decision"],
            reason_code=data["reason_code"],
            reason_text=data["reason_text"],
            row_version=data["rowVersion"],
            correlation_id=get_correlation_id(),
        )
        return Response(QuoteSerializer(updated).data)


class QuoteHistoryView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/history`: `getQuoteHistory` (GET)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        history = quote_service.get_quote_history(quote=quote)
        return Response(StateHistoryItemSerializer(history, many=True).data)


@requires_idempotency
class QuoteCancelView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/cancel`: `cancelQuote` (POST)."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = CancelQuoteRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = quote_service.cancel_quote(
            quote=quote,
            reason_code=data["reason_code"],
            reason_text=data["reason_text"],
            row_version=data["rowVersion"],
            correlation_id=get_correlation_id(),
        )
        return Response(QuoteSerializer(updated).data)


@requires_idempotency
class QuoteProposalView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}/proposal`: `generateQuoteProposal`
    (POST, 202), `getQuoteProposal` (GET)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)()]
        return [require_scope(Scope.READ)()]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        document = document_service.generate_quote_proposal(quote=quote)
        return Response(DocumentSerializer(document).data, status=202)

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        document = document_service.get_quote_proposal(quote=quote)
        if document is None:
            raise Http404
        return Response(DocumentSerializer(document).data)


@requires_idempotency
class DocumentTemplateListCreateView(APIView):
    """Pragmatic V1 addition, not in ART-006 (see
    apps/quote/application/document_service.py module docstring) — the
    only way to make `generateQuoteProposal` succeed at all, since OD-006
    has no approved template and ART-006 has no CRUD for this resource.
    `GET` (list) is a further pragmatic addition (same rationale as
    RuleVersionCreateView) so the admin/configurador UI has something to
    render before publishing a new template version."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def get(self, request):
        queryset = DocumentTemplateVersion.objects.order_by("template_code", "-version_no")
        template_code = request.query_params.get("templateCode")
        if template_code:
            queryset = queryset.filter(template_code=template_code)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(DocumentTemplateHeaderSerializer(page, many=True).data)

    def post(self, request):
        body = DocumentTemplateCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        template = document_service.create_document_template(
            template_code=data["template_code"],
            storage_ref=data["storage_ref"],
            effective_from=data["effective_from"],
            effective_to=data["effective_to"],
        )
        return Response(DocumentTemplateHeaderSerializer(template).data, status=201)


@requires_idempotency
class DocumentTemplatePublishView(APIView):
    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def post(self, request, template_id):
        template = get_object_or_404(DocumentTemplateVersion, id=template_id)
        published = document_service.publish_document_template(template)
        return Response(DocumentTemplateHeaderSerializer(published).data)


class ReviewQueueView(APIView):
    """ART-006 `/api/v1/reviews`: `listReviews` (GET) — the reviewer/approver
    worklist."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_REVIEW)]

    def get(self, request):
        queryset = ReviewTask.objects.all().order_by("created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ReviewTaskSerializer(page, many=True).data)
