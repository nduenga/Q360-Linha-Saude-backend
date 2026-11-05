from __future__ import annotations

import datetime

from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.report_excel import XLSX_CONTENT_TYPE, render_report_excel
from apps.foundation.application.report_pdf import REPORTS, render_report
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope
from apps.policy.infrastructure.models import Policy
from apps.product.infrastructure.models import PlanBenefit
from apps.quote.infrastructure.models import Quote
from apps.foundation.interfaces.report_serializers import (
    IssuanceReportSerializer,
    TopCoverageReportRowSerializer,
    TopProductReportRowSerializer,
)


def _report_date_filters(request) -> tuple[datetime.date | None, datetime.date | None]:
    date_field = serializers.DateField()
    values: dict[str, datetime.date | None] = {}
    for query_name in ("from", "to"):
        raw_value = request.query_params.get(query_name)
        if raw_value in (None, ""):
            values[query_name] = None
            continue
        try:
            values[query_name] = date_field.run_validation(raw_value)
        except serializers.ValidationError as exc:
            raise ValidationError({query_name: exc.detail}) from exc

    date_from, date_to = values["from"], values["to"]
    if date_from and date_to and date_from > date_to:
        raise ValidationError({"to": "A data final tem de ser igual ou posterior à data inicial."})
    return date_from, date_to


def _filter_quotes_by_date(queryset, date_from, date_to):
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def _filter_policies_by_start_date(queryset, date_from, date_to):
    if date_from:
        queryset = queryset.filter(start_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(start_date__lte=date_to)
    return queryset


def _status_counts(queryset) -> list[dict[str, int | str]]:
    return list(
        queryset.order_by()
        .values("status")
        .annotate(count=Count("id"))
        .order_by("-count", "status")
    )


def _top_products_data(tenant_id, date_from, date_to) -> list[dict]:
    quotes = _filter_quotes_by_date(
        Quote.objects.filter(
            plan__tenant_id=tenant_id,
            plan__product__tenant_id=tenant_id,
        ),
        date_from,
        date_to,
    )
    rows = (
        quotes.order_by()
        .values("plan__product_id", "plan__product__name")
        .annotate(
            quote_count=Count("id"),
            issued_count=Count("id", filter=Q(status="BOUND")),
        )
        .order_by("-quote_count", "plan__product__name")
    )
    return [
        {
            "productId": row["plan__product_id"],
            "productName": row["plan__product__name"],
            "quoteCount": row["quote_count"],
            "issuedCount": row["issued_count"],
        }
        for row in rows
    ]


def _top_coverages_data(tenant_id, date_from, date_to) -> list[dict]:
    quoted_plan_ids = _filter_quotes_by_date(
        Quote.objects.filter(plan__tenant_id=tenant_id),
        date_from,
        date_to,
    ).order_by().values("plan_id").distinct()
    rows = (
        PlanBenefit.objects.filter(
            plan_id__in=quoted_plan_ids,
            plan__tenant_id=tenant_id,
            benefit__tenant_id=tenant_id,
        )
        .order_by()
        .values("benefit_id", "benefit__name", "benefit__benefit_type")
        .annotate(plan_count=Count("plan_id", distinct=True))
        .order_by("-plan_count", "benefit__name")
    )
    return [
        {
            "benefitId": row["benefit_id"],
            "benefitName": row["benefit__name"],
            "category": row["benefit__benefit_type"],
            "planCount": row["plan_count"],
        }
        for row in rows
    ]


def _issuance_data(tenant_id, date_from, date_to) -> dict:
    quotes = _filter_quotes_by_date(
        Quote.objects.filter(plan__tenant_id=tenant_id),
        date_from,
        date_to,
    )
    policies = _filter_policies_by_start_date(
        Policy.objects.filter(plan__tenant_id=tenant_id),
        date_from,
        date_to,
    )
    return {
        "totalQuotes": quotes.count(),
        "totalPolicies": policies.count(),
        "quotesByStatus": _status_counts(quotes),
        "policiesByStatus": _status_counts(policies),
    }


_REPORT_DATA = {
    "top-products": _top_products_data,
    "top-coverages": _top_coverages_data,
    "issuance": _issuance_data,
}


class TopProductsReportView(APIView):
    """Relatório de produtos mais cotados, agrupado pelo produto associado ao plano."""

    permission_classes = [IsAuthenticated, require_scope(Scope.AUDIT)]

    def get(self, request):
        date_from, date_to = _report_date_filters(request)
        data = _top_products_data(CurrentTenantProvider.require().value, date_from, date_to)
        return Response(TopProductReportRowSerializer(data, many=True).data)


class TopCoveragesReportView(APIView):
    """Relatório de coberturas presentes nos planos com cotações no período."""

    permission_classes = [IsAuthenticated, require_scope(Scope.AUDIT)]

    def get(self, request):
        date_from, date_to = _report_date_filters(request)
        data = _top_coverages_data(CurrentTenantProvider.require().value, date_from, date_to)
        return Response(TopCoverageReportRowSerializer(data, many=True).data)


class IssuanceReportView(APIView):
    """Resumo de cotações criadas e apólices iniciadas, agrupadas por estado."""

    permission_classes = [IsAuthenticated, require_scope(Scope.AUDIT)]

    def get(self, request):
        date_from, date_to = _report_date_filters(request)
        data = _issuance_data(CurrentTenantProvider.require().value, date_from, date_to)
        return Response(IssuanceReportSerializer(data).data)


def _report_download(request, report, render, content_type) -> HttpResponse:
    if report not in REPORTS:
        raise Http404
    date_from, date_to = _report_date_filters(request)
    tenant_id = CurrentTenantProvider.require().value
    content, filename = render(
        report, _REPORT_DATA[report](tenant_id, date_from, date_to),
        tenant_id=tenant_id, date_from=date_from, date_to=date_to,
    )
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ReportPdfView(APIView):
    """Exporta para PDF os mesmos dados que o relatório mostra no ecrã."""

    permission_classes = [IsAuthenticated, require_scope(Scope.AUDIT)]

    def get(self, request, report):
        return _report_download(request, report, render_report, "application/pdf")


class ReportExcelView(APIView):
    """Exporta para Excel os mesmos dados que o relatório mostra no ecrã."""

    permission_classes = [IsAuthenticated, require_scope(Scope.AUDIT)]

    def get(self, request, report):
        return _report_download(request, report, render_report_excel, XLSX_CONTENT_TYPE)
