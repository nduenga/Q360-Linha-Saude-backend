"""`/api/v1/claims/...` — sinistralidade (R2). Dados de saúde: leitura só com
`quote:review` (subscritores sem essa permissão não veem sinistros), importação
e premissas só com `pricing-config:manage`, tudo em auditoria."""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.claims.application import import_service, projection_service, summary_service
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from shared.pagination import Q360PageNumberPagination

# Dados de saúde: só quem tem audit:read (Administrador e Gestor de subscrição).
READ = [require_scope(Scope.READ), require_permission(Permission.AUDIT_READ)]
MANAGE = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]


class ImportSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    proposerId = serializers.UUIDField(source="proposer_id")
    policyId = serializers.UUIDField(source="policy_id", allow_null=True)
    source = serializers.CharField()
    fileName = serializers.CharField(source="file_name")
    totalRows = serializers.IntegerField(source="total_rows")
    importedRows = serializers.IntegerField(source="imported_rows")
    errorRows = serializers.IntegerField(source="error_rows")
    errors = serializers.JSONField(source="errors_json")
    createdBy = serializers.CharField(source="created_by")
    createdAt = serializers.DateTimeField(source="created_at")


class AssumptionSetSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    assumptions = serializers.JSONField(source="params_json")
    createdBy = serializers.CharField(source="created_by")
    createdAt = serializers.DateTimeField(source="created_at")


class AssumptionSetRequestSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200)
    assumptions = serializers.JSONField()


class ProjectionRequestSerializer(serializers.Serializer):
    proposerId = serializers.UUIDField()
    policyId = serializers.UUIDField(required=False, allow_null=True, default=None)
    assumptionSetId = serializers.UUIDField(required=False, allow_null=True, default=None)
    assumptions = serializers.JSONField(required=False, allow_null=True, default=None)
    currency = serializers.CharField(required=False, default="AOA")


class ProjectionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    proposerId = serializers.UUIDField(source="proposer_id")
    policyId = serializers.UUIDField(source="policy_id", allow_null=True)
    assumptionSetId = serializers.UUIDField(source="assumption_set_id", allow_null=True)
    assumptions = serializers.JSONField(source="params_json")
    result = serializers.JSONField(source="result_json")
    createdBy = serializers.CharField(source="created_by")
    createdAt = serializers.DateTimeField(source="created_at")


def _date_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        raise summary_service.ClaimsDataError(f"'{name}' must be YYYY-MM-DD") from None


def _required_uuid(request, name):
    raw = request.query_params.get(name)
    try:
        return uuid.UUID(raw)
    except (TypeError, ValueError):
        raise summary_service.ClaimsDataError(f"'{name}' is required and must be a UUID") from None


def _optional_uuid(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise summary_service.ClaimsDataError(f"'{name}' must be a UUID") from None


def _group_default(field: str, fallback: str) -> str:
    """Limite/quota acordados em `group.rules` (negócio); sem configuração
    publicada, o exemplo do PDF (65 % / 100 %)."""
    from apps.business_config.application.readers import BusinessSnapshot

    value = (BusinessSnapshot.load().get("group.rules") or {}).get(field)
    return str(value) if value not in (None, "") else fallback


def _decimal_param(request, name, default):
    raw = request.query_params.get(name, default)
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise summary_service.ClaimsDataError(f"'{name}' must be a decimal") from None
    if not value.is_finite() or not Decimal("0") <= value <= Decimal("100"):
        raise summary_service.ClaimsDataError(f"'{name}' must be between 0 and 100")
    return value


@requires_idempotency
class ClaimsImportListCreateView(APIView):
    """POST (multipart: `file`, `kind`=CLAIMS|PREMIUMS, `proposerId`, optional
    `policyId`, `source`=INTERNAL|OTHER_INSURER, `dryRun`) imports CSV/XLSX;
    invalid rows are reported and skipped. GET lists imports and accepts
    optional `proposerId` and `policyId` filters."""

    parser_classes = [MultiPartParser]

    def get_permissions(self):
        return [p() for p in (MANAGE if self.request.method == "POST" else READ)]

    def get(self, request):
        queryset = import_service.list_imports(
            proposer_id=_optional_uuid(request, "proposerId"),
            policy_id=_optional_uuid(request, "policyId"),
        )
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ImportSerializer(page, many=True).data)

    def post(self, request):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response({"file": "This field is required."}, status=400)
        try:
            proposer_id = uuid.UUID(str(request.data.get("proposerId")))
            policy_raw = request.data.get("policyId")
            policy_id = uuid.UUID(str(policy_raw)) if policy_raw else None
        except ValueError:
            return Response({"proposerId": "proposerId (and policyId) must be UUIDs."}, status=400)
        result = import_service.import_file(
            kind=str(request.data.get("kind", "")).upper(), proposer_id=proposer_id, policy_id=policy_id,
            source=str(request.data.get("source", "INTERNAL")).upper(), filename=uploaded.name, content=uploaded.read(),
            dry_run=str(request.data.get("dryRun", "false")).lower() in ("1", "true", "yes"),
        )
        return Response(result, status=200 if result["dryRun"] else 201)


class ClaimsImportDetailView(APIView):
    permission_classes = READ

    def get(self, request, import_id):
        return Response(ImportSerializer(import_service.get_import(import_id)).data)


class ClaimsSummaryView(APIView):
    """GET /claims/summary?proposerId=&policyId=&from=&to=&currency= -
    loss ratio, frequency, average cost, by coverage and month, history
    months. Aggregates only."""

    permission_classes = READ

    def get(self, request):
        return Response(
            summary_service.summary(
                proposer_id=_required_uuid(request, "proposerId"), policy_id=_optional_uuid(request, "policyId"),
                date_from=_date_param(request, "from"), date_to=_date_param(request, "to"),
                currency=request.query_params.get("currency", "AOA").upper(),
            )
        )


class ClaimsMethodologyView(APIView):
    """GET /claims/methodology - the projection method in use (labelled
    indicative), its formulas and the accepted import formats."""

    permission_classes = READ

    def get(self, request):
        return Response(projection_service.methodology())


class ClaimsImportTemplateView(APIView):
    """GET /claims/import-template?kind=CLAIMS|PREMIUMS - a CSV with the
    accepted header and one example row."""

    permission_classes = READ

    def get(self, request):
        from django.http import HttpResponse

        from apps.claims.application import import_service

        kind = request.query_params.get("kind", "CLAIMS").upper()
        response = HttpResponse(import_service.import_template_csv(kind), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="modelo-{kind.lower()}.csv"'
        return response


class ClaimsProfitSharingView(APIView):
    """GET /claims/profit-sharing?proposerId=&thresholdPct=65&sharePct=100 -
    participação nos resultados do grupo (devolução de parte do prémio se a
    sinistralidade ficar abaixo do limite acordado). Override percentages
    must be between 0 and 100, inclusive."""

    permission_classes = READ

    def get(self, request):
        return Response(
            summary_service.profit_sharing(
                proposer_id=_required_uuid(request, "proposerId"), policy_id=_optional_uuid(request, "policyId"),
                threshold_pct=_decimal_param(request, "thresholdPct", _group_default("experience_loss_ratio_threshold", "65")),
                share_pct=_decimal_param(request, "sharePct", _group_default("profit_share_percent", "100")),
                date_from=_date_param(request, "from"), date_to=_date_param(request, "to"),
                currency=request.query_params.get("currency", "AOA").upper(),
            )
        )


class ClaimsProfitSharingParametersView(APIView):
    """GET /claims/profit-sharing/parameters - thresholds from current
    published group.rules, with the documented 65% / 100% fallbacks."""

    permission_classes = READ

    def get(self, request):
        values = []
        for name, field, fallback in (
            ("thresholdPct", "experience_loss_ratio_threshold", "65"),
            ("sharePct", "profit_share_percent", "100"),
        ):
            value = Decimal(_group_default(field, fallback))
            if not value.is_finite() or not Decimal("0") <= value <= Decimal("100"):
                raise summary_service.ClaimsDataError(f"Configured {name} must be between 0 and 100")
            values.append(value.quantize(Decimal("0.01")))
        return Response({"thresholdPct": str(values[0]), "sharePct": str(values[1])})


class AssumptionSetListCreateView(APIView):
    def get_permissions(self):
        return [p() for p in (MANAGE if self.request.method == "POST" else READ)]

    def get(self, request):
        from apps.claims.infrastructure.models import ProjectionAssumptionSet

        return Response(AssumptionSetSerializer(ProjectionAssumptionSet.objects.order_by("name"), many=True).data)

    def post(self, request):
        body = AssumptionSetRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        created = projection_service.create_assumption_set(name=body.validated_data["name"], params=body.validated_data["assumptions"])
        return Response(AssumptionSetSerializer(created).data, status=201)


class AssumptionSetDetailView(APIView):
    permission_classes = READ

    def get(self, request, set_id):
        return Response(AssumptionSetSerializer(projection_service.get_assumption_set(set_id)).data)


class ProjectionListCreateView(APIView):
    """POST /claims/projections - OPTIMISTIC/BASE/PESSIMISTIC projection from
    a saved assumption set or inline `assumptions`. GET accepts optional
    `proposerId` and `policyId` filters."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_REVIEW)()]
        return [p() for p in READ]

    def get(self, request):
        from apps.claims.infrastructure.models import ProjectionRun

        queryset = ProjectionRun.objects.order_by("-created_at")
        proposer_id = _optional_uuid(request, "proposerId")
        if proposer_id:
            queryset = queryset.filter(proposer_id=proposer_id)
        policy_id = _optional_uuid(request, "policyId")
        if policy_id:
            queryset = queryset.filter(policy_id=policy_id)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ProjectionSerializer(page, many=True).data)

    def post(self, request):
        body = ProjectionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        run = projection_service.run_projection(
            proposer_id=data["proposerId"], policy_id=data["policyId"], assumption_set_id=data["assumptionSetId"],
            assumptions=data["assumptions"], currency=data["currency"].upper(),
        )
        return Response(ProjectionSerializer(run).data, status=201)


class ProjectionDetailView(APIView):
    permission_classes = READ

    def get(self, request, run_id):
        return Response(ProjectionSerializer(projection_service.get_run(run_id)).data)
