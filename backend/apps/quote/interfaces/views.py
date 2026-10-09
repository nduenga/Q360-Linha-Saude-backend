"""Controllers for the quote module. Every `security` scope and permission
combination below is copied from ART-006's `security` block per
`operationId`, cross-checked against
docs/artifacts/ART-006-openapi/ — plus DOC-001 s18 `quote:*` permissions
(all already defined in Sprint 1, see apps/foundation/domain/permissions.py).
"""
from __future__ import annotations

import json
import uuid

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application.permission_evaluator import PermissionEvaluator
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.pricing.interfaces.serializers import PricingResponseSerializer, render_preview
from apps.quote.application import document_links
from apps.quote.application import (
    config_impact_service,
    document_service,
    proposal_service,
    quote_lifecycle_service,
    quote_service,
    quote_version_service,
    requirements_service,
    scenario_service,
    simulator_service,
)
from apps.quote.domain.enums import QuoteDecisionType
from apps.quote.infrastructure.models import DocumentTemplateVersion, Quote, ReviewTask
from apps.quote.interfaces.serializers import (
    AdjustmentRemoveRequestSerializer,
    AdjustmentRequestSerializer,
    CancelQuoteRequestSerializer,
    DecisionRequestSerializer,
    DocumentSerializer,
    DocumentTemplateCreateRequestSerializer,
    DocumentTemplateHeaderSerializer,
    DocumentTemplateUpdateRequestSerializer,
    PreExistingDecisionRequestSerializer,
    ProposalDocumentSerializer,
    ProposalRequestSerializer,
    QuoteAdjustmentSerializer,
    QuoteCloneRequestSerializer,
    QuoteCreateRequestSerializer,
    QuoteIndexationRequestSerializer,
    QuoteRenewalRequestSerializer,
    QuoteVersionDetailSerializer,
    QuoteVersionSaveRequestSerializer,
    QuoteVersionSerializer,
    QuoteMemberRequestSerializer,
    QuoteMemberSerializer,
    QuotePreviewRequestSerializer,
    QuotePriceRequestSerializer,
    QuoteSelectionRequestSerializer,
    QuoteSerializer,
    ScenarioApplyRequestSerializer,
    ScenarioCloneRequestSerializer,
    ScenarioCreateRequestSerializer,
    ScenarioSerializer,
    ScenarioUpdateRequestSerializer,
    QuoteSubmitRequestSerializer,
    QuoteUpdateRequestSerializer,
    ReviewTaskSerializer,
    StateHistoryItemSerializer,
)
from apps.quote.domain import proposal_template
from apps.quote.domain.proposal_template import default_body
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
        queryset = Quote.objects.select_related("latest_pricing_run").order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        # ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 4 (OD-ANGOLA-005) is
        # SUPERSEDED by DECISIONS_TAKEN.md#S09-POLICY-001 (2026-09-26):
        # "apólice" is no longer the quoteNumber of an approved Quote — a
        # real `Policy` entity (apps.policy) now exists, created only on
        # signature (ROADMAP_APOLICES.md Fases 2-4). This filter is kept
        # as a pragmatic lookup for the *quote* itself (still useful for
        # underwriting/backoffice screens that need to resolve a quote's
        # full context from its number), never as a policy lookup.
        quote_number = request.query_params.get("quoteNumber")
        if quote_number:
            queryset = queryset.filter(quote_number=quote_number)
        quote_type = request.query_params.get("quoteType")
        if quote_type:
            queryset = queryset.filter(quote_type=quote_type)
        source_policy_id = request.query_params.get("sourcePolicyId")
        if source_policy_id:
            queryset = queryset.filter(source_policy_id=source_policy_id)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(QuoteSerializer(page, many=True).data)

    def post(self, request):
        body = QuoteCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        quote = quote_service.create_quote(
            proposer_id=data.get("proposerId"),
            proposer_input=data.get("proposerInput"),
            titular_member_input=data.get("titularMemberInput"),
            plan_id=data["planId"],
            effective_date=data["effectiveDate"],
        )
        return Response(QuoteSerializer(quote).data, status=201)


@requires_idempotency
class QuoteDetailView(APIView):
    """ART-006 `/api/v1/quotes/{quoteId}`: `getQuote` (GET), `updateQuote` (PUT).
    Pragmatic DELETE extension (see apps/quote/application/quote_service.delete_quote):
    only non-protected statuses (DRAFT / READY / REJECTED / EXPIRED / CANCELLED)
    can actually be deleted; APPROVED/IN_REVIEW/BOUND raise QUOTE-DELETE-BLOCKED."""

    def get_permissions(self):
        if self.request.method == "PUT":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)()]
        if self.request.method == "DELETE":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        quote = get_object_or_404(
            Quote.objects.select_related("latest_pricing_run"), id=quote_id
        )
        return Response(QuoteSerializer(quote).data)

    def put(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = quote_service.update_quote(quote=quote, effective_date=data["effectiveDate"], row_version=data["rowVersion"])
        return Response(QuoteSerializer(updated).data)

    def delete(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        quote_service.delete_quote(quote=quote)
        return Response(status=204)


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
            raise PermissionDenied(f"O utilizador não tem a permissão {required_permission.value} para a decisão {data['decision']}")

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
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)

        history = list(
            quote_service.get_quote_history(quote=quote)
        )

        from uuid import UUID
        from apps.staff_accounts.infrastructure.models import StaffAccount

        actor_ids = []

        for item in history:
            try:
                actor_ids.append(UUID(str(item.changed_by)))
            except (TypeError, ValueError, AttributeError):
                # Pode ser um actor técnico:
                # system:auto, system-scheduler, etc.
                continue

        responsible_names = {
            str(row["id"]): row["name"]
            for row in (
                StaffAccount.objects
                .filter(
                    id__in=actor_ids,
                    tenant_id=quote.tenant_id,
                )
                .values("id", "name")
            )
        }

        return Response(
            StateHistoryItemSerializer(
                history,
                many=True,
                context={
                    "responsible_names": responsible_names,
                },
            ).data
        )

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

    def get_permissions(self):
        # Reading published template choices is needed by proposal generation
        # for any user with normal read access; mutations remain admin-only.
        if self.request.method == "GET":
            return [require_scope(Scope.READ)()]
        return [permission() for permission in self.permission_classes]

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


@requires_idempotency
class DocumentTemplateDetailView(APIView):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6, pragmatic V1 addition, not
    in ART-006. `PATCH`/`DELETE` only work while `status=DRAFT`."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def patch(self, request, template_id):
        template = get_object_or_404(DocumentTemplateVersion, id=template_id)
        body = DocumentTemplateUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = document_service.update_document_template(
            template, storage_ref=body.validated_data["storage_ref"]
        )
        return Response(DocumentTemplateHeaderSerializer(updated).data)

    def delete(self, request, template_id):
        template = get_object_or_404(DocumentTemplateVersion, id=template_id)
        document_service.delete_document_template(template)
        return Response(status=204)


@requires_idempotency
class DocumentTemplateRetireView(APIView):
    """OD-ANGOLA-006: the safe way to take a PUBLISHED template out of use
    — marks it RETIRED, never deletes the row (a Document already
    generated from it must keep resolving it)."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def post(self, request, template_id):
        template = get_object_or_404(DocumentTemplateVersion, id=template_id)
        retired = document_service.retire_document_template(template)
        return Response(DocumentTemplateHeaderSerializer(retired).data)


class ReviewQueueView(APIView):
    """ART-006 `/api/v1/reviews`: `listReviews` (GET) — the reviewer/approver
    worklist."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_REVIEW)]

    def get(self, request):
        queryset = ReviewTask.objects.select_related(
            "quote__proposer",
            "quote__plan__product",
        ).order_by("created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ReviewTaskSerializer(page, many=True).data)


@requires_idempotency
class QuoteSelectionView(APIView):
    """`PUT /quotes/{id}/selection` — optional coverages chosen by the
    customer (PDF "O"), the A-E participation option and "what if" capital
    overrides. Re-prices the quote (it returns to READY when it was ready)."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response({"selection": quote.selection_json, "rowVersion": quote.row_version})

    def put(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteSelectionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated, warnings = simulator_service.set_selection(
            quote=quote, selection=body.validated_data["selection"], row_version=body.validated_data["rowVersion"]
        )
        return Response({**QuoteSerializer(updated).data, "warnings": warnings})


class QuotePreviewView(APIView):
    """`POST /quotes/{id}/preview` — recalculates with a different selection
    and/or extra adjustments WITHOUT saving anything (no pricing run, audit
    or outbox); answers with the full calculation, the saved baseline and the
    delta."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CALCULATE)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuotePreviewRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        result = simulator_service.preview_quote(
            quote=quote,
            selection=body.validated_data["selection"],
            extra_adjustments=body.validated_data["adjustments"],
            render=render_preview,
        )
        return Response(result)


@requires_idempotency
class QuoteAdjustmentListCreateView(APIView):
    """`GET` lists the adjustments (agravamentos/descontos). `POST` applies
    one (reason required, re-prices) — or only simulates it with
    `?dryRun=true`."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_CALCULATE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        adjustments = simulator_service.list_adjustments(quote=quote, status=request.query_params.get("status"))
        return Response(QuoteAdjustmentSerializer(adjustments, many=True).data)

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = AdjustmentRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        spec = {"kind": data["kind"], "value": data["value"], "scope": data["scope"], "memberId": data["memberId"]}
        if str(request.query_params.get("dryRun", "false")).lower() in ("1", "true", "yes"):
            return Response(simulator_service.simulate_adjustment(quote=quote, spec={**spec, "reason": data["reason"]}))
        adjustment, updated = simulator_service.apply_adjustment(quote=quote, spec=spec, reason=data["reason"])
        return Response(
            {
                "adjustment": QuoteAdjustmentSerializer(adjustment).data,
                "quote": QuoteSerializer(updated).data,
                "impact": adjustment.impact_json,
            },
            status=201,
        )


@requires_idempotency
class QuoteAdjustmentDetailView(APIView):
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CALCULATE)]

    def delete(self, request, quote_id, adjustment_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = AdjustmentRemoveRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        adjustment, updated = simulator_service.remove_adjustment(
            quote=quote, adjustment_id=adjustment_id, reason=body.validated_data["reason"]
        )
        return Response({"adjustment": QuoteAdjustmentSerializer(adjustment).data, "quote": QuoteSerializer(updated).data})


@requires_idempotency
class QuoteMemberPreExistingView(APIView):
    """`PUT /quotes/{id}/members/{memberId}/pre-existing` — the underwriting
    decision for a pre-existing condition (6 treatments of the PDF);
    `DELETE` clears it. Both need a reason and re-price the quote."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def put(self, request, quote_id, member_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = PreExistingDecisionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        quote_member, updated, warnings = simulator_service.set_member_pre_existing(
            quote=quote, member_id=member_id, decision=body.validated_data["decision"], reason=body.validated_data["reason"]
        )
        return Response(
            {"memberId": str(member_id), "preExisting": quote_member.pre_existing_json, "quote": QuoteSerializer(updated).data, "warnings": warnings}
        )

    def delete(self, request, quote_id, member_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = AdjustmentRemoveRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = simulator_service.clear_member_pre_existing(quote=quote, member_id=member_id, reason=body.validated_data["reason"])
        return Response(QuoteSerializer(updated).data)


def _ids_param(request) -> list[uuid.UUID] | None:
    raw = request.query_params.get("ids")
    if not raw:
        return None
    try:
        return [uuid.UUID(part) for part in raw.split(",") if part]
    except ValueError:
        raise PermissionDenied("ids tem de ser uma lista de ids de cenários separados por vírgula") from None


@requires_idempotency
class QuoteScenarioListCreateView(APIView):
    """R5: GET lists the scenarios of a quote (with `stale` when their stored
    result no longer matches the current plan/tariffs/population); POST
    creates one (from the current state of the quote unless `parameters` is
    given) and calculates it."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_CALCULATE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(ScenarioSerializer(scenario_service.list_scenarios(quote=quote), many=True).data)

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = ScenarioCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        scenario = scenario_service.create_scenario(
            quote=quote, name=data["name"], description=data["description"], parameters=data["parameters"], render=render_preview
        )
        return Response(ScenarioSerializer(scenario).data, status=201)


class QuoteScenarioCompareView(APIView):
    """GET /quotes/{id}/scenarios/compare?ids=a,b - side by side: total premium
    and delta, coverages (capital, participation, waiting days) with what
    differs, premium components, adjustments and the A-E option."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(scenario_service.compare_scenarios(quote=quote, scenario_ids=_ids_param(request)))


class QuoteScenarioCompareExportView(APIView):
    """GET /quotes/{id}/scenarios/compare/export?fileType=xlsx|csv&ids=..."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        import csv
        import io

        quote = get_object_or_404(Quote, id=quote_id)
        comparison = scenario_service.compare_scenarios(quote=quote, scenario_ids=_ids_param(request))
        sheets = scenario_service.comparison_sheets(comparison)
        file_type = request.query_params.get("fileType", "xlsx").lower()
        if file_type == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            for title, rows in sheets.items():
                writer.writerow([f"# {title}"])
                writer.writerows(rows)
                writer.writerow([])
            response = HttpResponse(buffer.getvalue().encode("utf-8-sig"), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="comparacao-cenarios.csv"'
            return response
        if file_type != "xlsx":
            return Response({"fileType": "Use xlsx or csv."}, status=400)
        from openpyxl import Workbook

        workbook = Workbook()
        workbook.remove(workbook.active)
        for title, rows in sheets.items():
            sheet = workbook.create_sheet(title)
            for row in rows:
                sheet.append(row)
        out = io.BytesIO()
        workbook.save(out)
        response = HttpResponse(
            out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="comparacao-cenarios.xlsx"'
        return response


@requires_idempotency
class ScenarioDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_CALCULATE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, scenario_id):
        return Response(ScenarioSerializer(scenario_service.get_scenario(scenario_id)).data)

    def patch(self, request, scenario_id):
        scenario = scenario_service.get_scenario(scenario_id)
        body = ScenarioUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = scenario_service.update_scenario(
            scenario=scenario,
            name=data["name"],
            description=data["description"],
            parameters=data["parameters"],
            row_version=data["rowVersion"],
            render=render_preview,
        )
        return Response(ScenarioSerializer(updated).data)

    def delete(self, request, scenario_id):
        scenario_service.delete_scenario(scenario=scenario_service.get_scenario(scenario_id))
        return Response(status=204)


class _ScenarioActionMixin:
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CALCULATE)]


@requires_idempotency
class ScenarioCloneView(_ScenarioActionMixin, APIView):
    def post(self, request, scenario_id):
        scenario = scenario_service.get_scenario(scenario_id)
        body = ScenarioCloneRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        clone = scenario_service.clone_scenario(scenario=scenario, name=body.validated_data["name"], render=render_preview)
        return Response(ScenarioSerializer(clone).data, status=201)


@requires_idempotency
class ScenarioRecalculateView(_ScenarioActionMixin, APIView):
    def post(self, request, scenario_id):
        scenario = scenario_service.get_scenario(scenario_id)
        return Response(ScenarioSerializer(scenario_service.recalculate_scenario(scenario=scenario, render=render_preview)).data)


@requires_idempotency
class ScenarioSelectView(_ScenarioActionMixin, APIView):
    def post(self, request, scenario_id):
        scenario = scenario_service.get_scenario(scenario_id)
        return Response(ScenarioSerializer(scenario_service.select_scenario(scenario=scenario)).data)


@requires_idempotency
class ScenarioApplyView(APIView):
    """POST /scenarios/{id}/apply - makes the scenario the official state of
    the quote (reason required, authority limits apply, quote is re-priced)."""

    permission_classes = [
        require_scope(Scope.WRITE),
        require_permission(Permission.QUOTE_CALCULATE),
        require_permission(Permission.QUOTE_EDIT),
    ]

    def post(self, request, scenario_id):
        scenario = scenario_service.get_scenario(scenario_id)
        body = ScenarioApplyRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        quote = scenario_service.apply_scenario(scenario=scenario, reason=body.validated_data["reason"])
        return Response(QuoteSerializer(quote).data)


@requires_idempotency
class QuoteRenewalCreateView(APIView):
    """POST /quotes/renewals - renewal proposal of an existing policy: the
    policy population (except people above the plan permanence age), the
    selection and pre-existing decisions of the source quote, previous
    premium/period as context."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CREATE)]

    def post(self, request):
        body = QuoteRenewalRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        renewal = quote_lifecycle_service.create_renewal(
            source_policy_id=data["sourcePolicyId"], effective_date=data["effectiveDate"], plan_id=data["planId"]
        )
        return Response(QuoteSerializer(renewal).data, status=201)


@requires_idempotency
class QuoteCloneView(APIView):
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CREATE)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteCloneRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        copy = quote_lifecycle_service.clone_quote(
            quote=quote, effective_date=body.validated_data["effectiveDate"], reason=body.validated_data["reason"]
        )
        return Response(QuoteSerializer(copy).data, status=201)


@requires_idempotency
class QuoteVersionListCreateView(APIView):
    """GET lists the versions of a quote (newest first); POST saves the
    current state as a manual version (reason required)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(QuoteVersionSerializer(quote_version_service.list_versions(quote=quote), many=True).data)

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteVersionSaveRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        version = quote_version_service.save_version(quote=quote, reason=body.validated_data["reason"])
        return Response(QuoteVersionSerializer(version).data, status=201)


class QuoteVersionDetailView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id, version_no):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(QuoteVersionDetailSerializer(quote_version_service.get_version(quote=quote, version_no=version_no)).data)


class QuoteVersionDiffView(APIView):
    """GET /quotes/{id}/versions/{n}/diff[?against=m] - what changed between
    version n and version m (or the current state)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id, version_no):
        quote = get_object_or_404(Quote, id=quote_id)
        against = request.query_params.get("against")
        return Response(
            quote_version_service.compare_versions(
                quote=quote, version_no=version_no, against=int(against) if against else None
            )
        )


@requires_idempotency
class QuoteVersionRestoreView(APIView):
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def post(self, request, quote_id, version_no):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteVersionSaveRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        restored, report = quote_version_service.restore_version(
            quote=quote, version_no=version_no, reason=body.validated_data["reason"]
        )
        return Response({"quote": QuoteSerializer(restored).data, **report})


class QuoteRequirementsView(APIView):
    """GET /quotes/{id}/requirements - underwriting requirements and alerts
    (clinical questionnaire, medical exams, age limits, group size, network
    coverage, prior authorization, evacuation terms, waiting periods,
    exclusions...) derived from the plan settings and the population."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(requirements_service.evaluate_requirements(quote))


@requires_idempotency
class QuoteIndexationView(APIView):
    """POST /quotes/{id}/renewal/indexation[?dryRun=true] - indexes the plan
    capitals by the medical inflation (PDF: review capitals on every
    renewal)."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT), require_permission(Permission.QUOTE_CALCULATE)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteIndexationRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        dry_run = str(request.query_params.get("dryRun", "false")).lower() in ("1", "true", "yes")
        result = quote_lifecycle_service.apply_indexation(
            quote=quote,
            pct=data["medicalInflationPct"],
            rounding=data["roundTo"],
            reason=data["reason"],
            dry_run=dry_run,
            render=render_preview,
        )
        if not dry_run:
            result["quote"] = QuoteSerializer(result["quote"]).data
        return Response(result)


class ConfigurationImpactSimulationView(APIView):
    """POST /configuration/{type}/{id}/impact-simulation - reprices the most
    recent quotes with the published configuration and with this version and
    summarises the premium impact, before publishing (nothing is saved)."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]

    def post(self, request, config_type, config_id):
        limit = request.data.get("limit", 50) if isinstance(request.data, dict) else 50
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            return Response({"limit": "Must be a positive integer."}, status=400)
        return Response(config_impact_service.simulate_impact(config_type=config_type, config_id=config_id, limit=limit))


def _file_response(data: bytes, content_type: str, name: str | None = None) -> HttpResponse:
    response = HttpResponse(data, content_type=content_type)
    if name:
        response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@requires_idempotency
class QuoteProposalListCreateView(APIView):
    """R8: POST generates a proposal (PDF/DOCX/HTML) from the selected
    scenario (or an explicit `scenarioId`, or the current quote) using a
    configurable template; GET lists the generated documents (history)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_CALCULATE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(ProposalDocumentSerializer(proposal_service.list_documents(quote=quote), many=True).data)

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = ProposalRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        document = proposal_service.generate(
            quote=quote, template_code=data["templateCode"], scenario_id=data["scenarioId"],
            fmt=data["format"].upper(), render=render_preview,
        )
        return Response(ProposalDocumentSerializer(document).data, status=201 if document.status == "GENERATED" else 200)


class QuoteProposalPreviewView(APIView):
    """GET /quotes/{id}/proposals/preview?scenarioId=&templateCode= - the
    proposal as HTML, nothing saved."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        scenario_id = request.query_params.get("scenarioId")
        data, content_type = proposal_service.preview(
            quote=quote, scenario_id=uuid.UUID(scenario_id) if scenario_id else None,
            template_code=request.query_params.get("templateCode"), fmt="HTML", render=render_preview,
        )
        return _file_response(data, content_type)


class DocumentDownloadView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, document_id):
        document = proposal_service.get_document(document_id)
        data = proposal_service.read_file(document)
        return _file_response(data, document.content_type or "application/octet-stream", document.file_name)


@requires_idempotency
class DocumentSignedUrlView(APIView):
    """POST /documents/{id}/signed-url - a time-limited link anyone can open
    (no sign-in) until it expires."""

    permission_classes = [require_scope(Scope.READ)]

    def post(self, request, document_id):
        return Response(document_links.create_link(document_id=document_id), status=201)


class DocumentSignedDownloadView(APIView):
    """GET /documents/signed/{token} - public; the signed token is the credential."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        data, content_type, name = document_links.open_link(token)
        return _file_response(data, content_type, name)


@requires_idempotency
class DocumentRetryView(APIView):
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CALCULATE)]

    def post(self, request, document_id):
        document = proposal_service.retry(document=proposal_service.get_document(document_id))
        return Response(ProposalDocumentSerializer(document).data)


class DocumentTemplatePreviewView(APIView):
    """GET /document-templates/{id}/preview[?fileType=html|pdf|docx] - the
    template laid out with sample data, before publishing."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def get(self, request, template_id):
        template = get_object_or_404(DocumentTemplateVersion, id=template_id)
        fmt = request.query_params.get("fileType", "html").upper()
        data, content_type = proposal_service.preview_template(template=template, fmt=fmt)
        return _file_response(data, content_type)


class DocumentTemplateSchemaView(APIView):
    """GET /document-templates/schema - what a template body may contain:
    the default body, the allowed sections and the allowed {{variables}}."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        return Response(
            {
                "defaultBody": json.loads(default_body()),
                "sections": proposal_template.SECTIONS,
                "variables": proposal_template.VARIABLES,
                "formats": list(proposal_service.FORMATS),
            }
        )


class QuoteClaimsContextView(APIView):
    """GET /quotes/{id}/claims-context - what the claims history says about
    this quote's client (loss ratio, frequency, months available — the 3
    years asked on transfer from another insurer) and the latest projections.
    Aggregates only; needs audit:read (health data)."""

    permission_classes = [require_scope(Scope.READ), require_permission(Permission.AUDIT_READ)]

    def get(self, request, quote_id):
        from apps.claims.application import summary_service
        from apps.claims.infrastructure.models import ProjectionRun

        quote = get_object_or_404(Quote, id=quote_id)
        months = summary_service.history_months(proposer_id=quote.proposer_id)
        projections = [
            {"id": str(r.id), "createdAt": r.created_at.isoformat(), "scenarios": {
                k: {"expectedLossRatioPct": v["expectedLossRatioPct"], "premiumImpactPct": v["premiumImpactPct"]}
                for k, v in r.result_json["scenarios"].items()}}
            for r in ProjectionRun.objects.filter(proposer_id=quote.proposer_id).order_by("-created_at")[:5]
        ]
        if months == 0:
            return Response({"available": False, "historyMonths": 0, "threeYearsAvailable": False, "projections": projections})
        data = summary_service.summary(proposer_id=quote.proposer_id)
        return Response(
            {"available": True, "historyMonths": months, "threeYearsAvailable": months >= 36, "summary": data, "projections": projections}
        )
