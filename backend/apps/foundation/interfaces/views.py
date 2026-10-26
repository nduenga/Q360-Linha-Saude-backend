"""GET /api/v1/me (Q360-S1-03, ART-006 operationId `getCurrentActor`)
and GET /api/v1/audit-events (ART-006 operationId `listAuditEvents`).

Response bodies match ART-006 schemas verbatim (DOC-004 s2 precedence
rule). See individual view docstrings for the exact operationId cross
reference.
"""
from __future__ import annotations

from django.db import connections
from django.db.models import Count, Q, F
from django.db.models.functions import TruncMonth, TruncWeek
from django.http import JsonResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.scopes import Scope
from apps.foundation.infrastructure.models import AuditEvent
from apps.foundation.interfaces.audit_serializers import AuditEventSerializer
from apps.foundation.interfaces.permissions import require_scope
from apps.policy.infrastructure.models import Policy
from apps.pricing.infrastructure.models import PricingRun
from apps.quote.infrastructure.models import Quote, ReviewTask
from shared.pagination import Q360PageNumberPagination
from apps.policy.interfaces.serializers import PolicySerializer
from apps.quote.interfaces.serializers import QuoteSerializer


class MeView(APIView):
    # ART-006 path /api/v1/me, operation `get`: security -> oauth2: [q360.read]
    permission_classes = [IsAuthenticated, require_scope(Scope.READ)]

    def get(self, request):
        actor = request.user.actor
        return Response(
            {
                "actorId": actor.actor_id,
                "tenantId": str(actor.tenant_id),
                "roles": sorted(role.value for role in actor.roles),
                "permissions": sorted(permission.value for permission in actor.permissions),
            }
        )


class AuditEventListView(APIView):
    """ART-006 `/api/v1/audit-events`, operationId `listAuditEvents`.

    Query filters are exactly those documented in ART-006 (`entityType`,
    `entityId`, `correlationId`) — no additional filtering is exposed
    here because the contract does not describe it. Tenant scoping is
    applied by the model's default manager via `TenantScopedModel`.
    """

    permission_classes = [IsAuthenticated, require_scope(Scope.AUDIT)]

    def get(self, request):
        queryset = AuditEvent.objects.all().order_by("-occurred_at")

        entity_type = request.query_params.get("entityType")
        entity_id = request.query_params.get("entityId")
        correlation_id = request.query_params.get("correlationId")
        actor_id = request.query_params.get("actorId")
        action = request.query_params.get("action")
        occurred_from = request.query_params.get("from")
        occurred_to = request.query_params.get("to")

        filters = Q()
        if entity_type:
            filters &= Q(entity_type=entity_type)
        if entity_id:
            filters &= Q(entity_id=entity_id)
        if correlation_id:
            filters &= Q(correlation_id=correlation_id)
        if actor_id:
            filters &= Q(actor_id=actor_id)
        if action:
            filters &= Q(action=action)
        if occurred_from:
            filters &= Q(occurred_at__gte=occurred_from)
        if occurred_to:
            filters &= Q(occurred_at__lte=occurred_to)
        if filters:
            queryset = queryset.filter(filters)

        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        from apps.foundation.application.audit_labels import entity_labels

        labels = entity_labels(page)
        return paginator.get_paginated_response(
            AuditEventSerializer(page, many=True, context={"entity_labels": labels}).data
        )


def _status_counts(queryset) -> dict[str, int]:
    # order_by() limpa a ordenação: senão o Django junta-a ao GROUP BY e
    # devolve uma linha por registo em vez de uma por estado.
    return {row["status"]: row["total"] for row in queryset.order_by().values("status").annotate(total=Count("id"))}


class DashboardView(APIView):
    """
    GET /api/v1/dashboard?page=0&size=20

    Dashboard operacional com:
    - Cotações paginadas
    - Dados de underwriting
    - Subscrições/apólices paginadas

    A paginação segue Q360PageNumberPagination:
        page=0 -> primeira página
        page=1 -> segunda página
        page=2 -> terceira página

    Cada cotação e subscrição retorna:
    - ID
    - nome/número
    - ID e nome do proponente
    - ID e nome do plano

    A subscrição também retorna:
    - ID e nome/número da cotação de origem
    """

    permission_classes = [IsAuthenticated, require_scope(Scope.READ)]

    def get(self, request):
        trend_period = request.query_params.get("trendPeriod", "month").lower()
        if trend_period not in {"week", "month"}:
            return Response({"detail": "trendPeriod tem de ser 'week' ou 'month'."}, status=400)
        # ==========================================================
        # QUERYSETS
        # ==========================================================

        quotes = (
            Quote.objects
            .select_related(
                "proposer",
                "plan",
            )
            .order_by("-created_at")
        )
        proposer_id = request.query_params.get("proposerId")
        if proposer_id:
            quotes = quotes.filter(proposer_id=proposer_id)

        policies = (
            Policy.objects
            .select_related(
                "proposer",
                "plan",
                "source_quote",
                "source_quote__proposer",
                "source_quote__plan",
            )
            .order_by("-issued_at")
        )

        review_tasks = ReviewTask.objects.all()

        pricing_runs = PricingRun.objects.all()

        # ==========================================================
        # PAGINAÇÃO DAS COTAÇÕES
        # ==========================================================

        quote_paginator = Q360PageNumberPagination()

        quote_page = quote_paginator.paginate_queryset(
            quotes,
            request,
            view=self,
        )

        quote_items = []

        for quote in quote_page:
            quote_items.append(
                {
                    # --------------------------------------------------
                    # COTAÇÃO
                    # --------------------------------------------------

                    "id": str(quote.id),

                    "name": (
                        quote.quote_number
                        or f"Cotação {quote.id}"
                    ),

                    "quoteNumber": quote.quote_number,

                    # --------------------------------------------------
                    # PROPONENTE
                    # --------------------------------------------------

                    "proposer": {
                        "id": str(quote.proposer_id),
                        "name": quote.proposer.display_name,
                    },

                    # Mantemos também o formato simples por
                    # compatibilidade com o frontend existente.
                    "proposerId": str(quote.proposer_id),

                    # --------------------------------------------------
                    # PLANO
                    # --------------------------------------------------

                    "plan": {
                        "id": str(quote.plan_id),
                        "name": quote.plan.name,
                        "code": quote.plan.code,
                    },

                    "planId": str(quote.plan_id),

                    # --------------------------------------------------
                    # PRODUTO / VERSÃO
                    # --------------------------------------------------

                    "productVersionId": (
                        str(quote.product_version_id)
                        if quote.product_version_id
                        else None
                    ),

                    # --------------------------------------------------
                    # ESTADO DA COTAÇÃO
                    # --------------------------------------------------

                    "status": quote.status,

                    "validUntil": quote.valid_until,

                    "currencyCode": quote.currency_code,

                    # --------------------------------------------------
                    # PRICING
                    # --------------------------------------------------

                    "latestPricingRunId": (
                        str(quote.latest_pricing_run_id)
                        if quote.latest_pricing_run_id
                        else None
                    ),

                    # --------------------------------------------------
                    # SUBMISSÃO
                    # --------------------------------------------------

                    "submittedBy": quote.submitted_by,

                    "submittedAt": quote.submitted_at,

                    # --------------------------------------------------
                    # APROVAÇÃO
                    # --------------------------------------------------

                    "approvedBy": quote.approved_by,

                    "approvedAt": quote.approved_at,

                    # --------------------------------------------------
                    # REJEIÇÃO
                    # --------------------------------------------------

                    "rejectedBy": quote.rejected_by,

                    "rejectedAt": quote.rejected_at,

                    # --------------------------------------------------
                    # CANCELAMENTO
                    # --------------------------------------------------

                    "cancellationReason": quote.cancellation_reason,

                    # --------------------------------------------------
                    # AUDITORIA / CONTROLO
                    # --------------------------------------------------

                    "createdBy": quote.created_by,

                    "createdAt": quote.created_at,

                    "updatedAt": quote.updated_at,

                    "rowVersion": quote.row_version,
                }
            )

        # Use persisted lifecycle timestamps; do not estimate missing durations.
        approval_pairs = quotes.filter(
            submitted_at__isnull=False,
            approved_at__isnull=False,
            approved_at__gte=F("submitted_at"),
        ).values_list("submitted_at", "approved_at")
        approval_durations = [
            (approved_at - submitted_at).total_seconds()
            for submitted_at, approved_at in approval_pairs
        ]
        average_approval_seconds = (
            sum(approval_durations) / len(approval_durations) if approval_durations else None
        )

        status_counts = _status_counts(quotes)
        total_quotes = sum(status_counts.values())
        approved_quotes = status_counts.get("APPROVED", 0) + status_counts.get("BOUND", 0)
        trunc_period = TruncWeek if trend_period == "week" else TruncMonth
        created_buckets = {
            row["period"].date().isoformat(): row["total"]
            for row in quotes.order_by().annotate(period=trunc_period("created_at")).values("period").annotate(total=Count("id"))
        }
        approved_buckets = {
            row["period"].date().isoformat(): row["total"]
            for row in quotes.filter(approved_at__isnull=False).order_by()
            .annotate(period=trunc_period("approved_at"))
            .values("period").annotate(total=Count("id"))
        }
        trend = [
            {"periodStart": day, "created": created_buckets.get(day, 0), "approved": approved_buckets.get(day, 0)}
            for day in sorted(created_buckets.keys() | approved_buckets.keys())
        ]
        product_conversion = []
        for row in quotes.order_by().values("plan__product_id", "plan__product__code", "plan__product__name").annotate(
            total=Count("id"),
            converted=Count("id", filter=Q(status__in=("APPROVED", "BOUND"))),
        ).order_by("plan__product__code"):
            product_conversion.append({
                "productId": str(row["plan__product_id"]),
                "productCode": row["plan__product__code"],
                "productName": row["plan__product__name"],
                "quotes": row["total"],
                "converted": row["converted"],
                "conversionRatePercent": round(row["converted"] / row["total"] * 100, 2) if row["total"] else None,
            })
        channel_conversion = []
        for row in quotes.order_by().values("source_channel").annotate(
            total=Count("id"),
            converted=Count("id", filter=Q(status__in=("APPROVED", "BOUND"))),
        ).order_by("source_channel"):
            channel_conversion.append({
                "sourceChannel": row["source_channel"],
                "attributionStatus": "UNATTRIBUTED" if row["source_channel"] is None else "ATTRIBUTED",
                "quotes": row["total"],
                "converted": row["converted"],
                "conversionRatePercent": round(row["converted"] / row["total"] * 100, 2) if row["total"] else None,
            })
        quotations = {
            "total": quote_paginator.total_elements,

            "byStatus": status_counts,

            "approvalMetrics": {
                "measuredQuotes": len(approval_durations),
                "averageDurationSeconds": round(average_approval_seconds, 2) if average_approval_seconds is not None else None,
                "averageDurationHours": round(average_approval_seconds / 3600, 2) if average_approval_seconds is not None else None,
                "approvedQuotes": approved_quotes,
                "conversionRatePercent": round(approved_quotes / total_quotes * 100, 2) if total_quotes else None,
                "conversionDefinition": "APPROVED or BOUND / all quotes in the current filter",
                "conversionByProduct": product_conversion,
                "conversionByChannel": channel_conversion,
            },
            "trend": {"period": trend_period.upper(), "items": trend},

            "items": quote_items,

            "page": {
                "page": quote_paginator.page,
                "size": quote_paginator.size,
                "totalElements": quote_paginator.total_elements,
                "totalPages": (
                    (
                        quote_paginator.total_elements
                        + quote_paginator.size
                        - 1
                    )
                    // quote_paginator.size
                    if quote_paginator.size
                    else 0
                ),
            },
        }

        # ==========================================================
        # UNDERWRITING
        # ==========================================================

        recent_pricing_runs = (
            pricing_runs
            .order_by("-created_at")[:5]
        )

        underwriting = {
            "reviewTasks": {
                "total": review_tasks.count(),

                "byStatus": _status_counts(
                    review_tasks
                ),

                "open": review_tasks.filter(
                    status="OPEN"
                ).count(),
            },

            "pricingRuns": {
                "total": pricing_runs.count(),

                "byStatus": _status_counts(
                    pricing_runs
                ),

                "recent": [
                    {
                        "id": str(run.id),

                        "planId": (
                            str(run.plan_id)
                            if run.plan_id
                            else None
                        ),

                        "status": run.status,

                        "totalAmount": run.total_amount,

                        "currencyCode": run.currency_code,

                        "createdAt": run.created_at,
                    }
                    for run in recent_pricing_runs
                ],
            },
        }

        # ==========================================================
        # PAGINAÇÃO DAS SUBSCRIÇÕES / APÓLICES
        # ==========================================================

        policy_paginator = Q360PageNumberPagination()

        policy_page = policy_paginator.paginate_queryset(
            policies,
            request,
            view=self,
        )

        subscription_items = []

        for policy in policy_page:
            # ------------------------------------------------------
            # COTAÇÃO DE ORIGEM
            # ------------------------------------------------------

            source_quote = policy.source_quote

            source_quote_name = (
                source_quote.quote_number
                or f"Cotação {source_quote.id}"
            )

            # ------------------------------------------------------
            # SUBSCRIÇÃO
            # ------------------------------------------------------

            subscription_name = (
                policy.policy_number
                or f"Subscrição {policy.id}"
            )

            subscription_items.append(
                {
                    # --------------------------------------------------
                    # SUBSCRIÇÃO
                    # --------------------------------------------------

                    "id": str(policy.id),

                    "name": subscription_name,

                    "policyNumber": policy.policy_number,

                    # --------------------------------------------------
                    # COTAÇÃO DE ORIGEM
                    # --------------------------------------------------

                    "sourceQuote": {
                        "id": str(source_quote.id),

                        "name": source_quote_name,

                        "quoteNumber": source_quote.quote_number,
                    },

                    "sourceQuoteId": str(
                        policy.source_quote_id
                    ),

                    # --------------------------------------------------
                    # PROPONENTE
                    # --------------------------------------------------

                    "proposer": {
                        "id": str(policy.proposer_id),

                        "name": policy.proposer.display_name,
                    },

                    "proposerId": str(
                        policy.proposer_id
                    ),

                    # --------------------------------------------------
                    # PLANO
                    # --------------------------------------------------

                    "plan": {
                        "id": str(policy.plan_id),

                        "name": policy.plan.name,

                        "code": policy.plan.code,
                    },

                    "planId": str(
                        policy.plan_id
                    ),

                    # --------------------------------------------------
                    # TIPO
                    # --------------------------------------------------

                    "policyType": policy.policy_type,

                    "termMonths": policy.term_months,

                    # --------------------------------------------------
                    # VIGÊNCIA
                    # --------------------------------------------------

                    "startDate": policy.start_date,

                    "endDate": policy.end_date,

                    "requestedStartDate": (
                        policy.requested_start_date
                    ),

                    # --------------------------------------------------
                    # ESTADO
                    # --------------------------------------------------

                    "status": policy.status,

                    # --------------------------------------------------
                    # PAGAMENTO
                    # --------------------------------------------------

                    "paymentFrequency": (
                        policy.payment_frequency
                    ),

                    "currencyCode": (
                        policy.currency_code
                    ),

                    # --------------------------------------------------
                    # CANCELAMENTO
                    # --------------------------------------------------

                    "cancellationReasonCode": (
                        policy.cancellation_reason_code
                    ),

                    "cancellationEffectiveDate": (
                        policy.cancellation_effective_date
                    ),

                    "cancelledBy": policy.cancelled_by,

                    "cancelledAt": policy.cancelled_at,

                    # --------------------------------------------------
                    # TERMINAÇÃO
                    # --------------------------------------------------

                    "terminationReasonCode": (
                        policy.termination_reason_code
                    ),

                    "terminatedAt": (
                        policy.terminated_at
                    ),

                    # --------------------------------------------------
                    # EMISSÃO
                    # --------------------------------------------------

                    "issuedBy": policy.issued_by,

                    "issuedAt": policy.issued_at,

                    # --------------------------------------------------
                    # CONTROLO
                    # --------------------------------------------------

                    "createdAt": policy.created_at,

                    "updatedAt": policy.updated_at,

                    "rowVersion": policy.row_version,
                }
            )

        subscriptions = {
            "total": policy_paginator.total_elements,

            "byStatus": _status_counts(
                policies
            ),

            "items": subscription_items,

            "page": {
                "page": policy_paginator.page,
                "size": policy_paginator.size,
                "totalElements": (
                    policy_paginator.total_elements
                ),
                "totalPages": (
                    (
                        policy_paginator.total_elements
                        + policy_paginator.size
                        - 1
                    )
                    // policy_paginator.size
                    if policy_paginator.size
                    else 0
                ),
            },
        }

        # ==========================================================
        # RESPOSTA FINAL
        # ==========================================================

        return Response(
            {
                "quotations": quotations,

                "underwriting": underwriting,

                "subscriptions": subscriptions,
            }
        )

class LiveHealthView(APIView):
    """Unauthenticated liveness probe: process is able to answer HTTP."""

    permission_classes = [AllowAny]

    def get(self, request):
        return JsonResponse({"status": "ok"})


class ReadyHealthView(APIView):
    """Readiness probe: verifies the configured database accepts a query."""

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return JsonResponse({"status": "unavailable"}, status=503)
        return JsonResponse({"status": "ok"})
