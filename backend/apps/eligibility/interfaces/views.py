"""ART-006 `/api/v1/eligibility/evaluate`: `evaluateEligibility` (POST),
security -> oauth2: [q360.write]. No DOC-001 s18 permission gates this
domain (not in the matrix), same as the client module."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.eligibility.interfaces.serializers import EligibilityRequestSerializer, EligibilityResponseSerializer
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_scope

from django.shortcuts import get_object_or_404
from django.db.models import Q

from apps.eligibility.infrastructure.models import EligibilityEvaluation
from shared.pagination import Q360PageNumberPagination

from .serializers import EligibilityExecutionSerializer

@requires_idempotency
class EligibilityEvaluateView(APIView):
    permission_classes = [require_scope(Scope.WRITE)]

    def post(self, request):
        body = EligibilityRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        evaluation = EvaluateEligibilityUseCase().execute(
            proposer_id=data["proposerId"],
            member_id=data["memberId"],
            plan_id=data["planId"],
            effective_date=data["effectiveDate"],
            context=data["context"],
            correlation_id=get_correlation_id(),
        )
        return Response(EligibilityResponseSerializer(evaluation).data, status=200)

class EligibilityExecutionListView(APIView):
    """
    GET /api/v1/eligibility/evaluations

    Lista avaliações de elegibilidade já executadas.
    """

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        queryset = EligibilityEvaluation.objects.all().order_by(
            "-evaluated_at"
        )

        decision = request.query_params.get("decision")
        member_id = request.query_params.get("memberId")
        proposer_id = request.query_params.get("proposerId")
        plan_id = request.query_params.get("planId")

        if decision:
            queryset = queryset.filter(decision=decision)

        if member_id:
            queryset = queryset.filter(member_id=member_id)

        if proposer_id:
            queryset = queryset.filter(proposer_id=proposer_id)

        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)

        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)

        return paginator.get_paginated_response(
            EligibilityExecutionSerializer(
                page,
                many=True,
            ).data
        )


class EligibilityExecutionDetailView(APIView):
    """
    GET /api/v1/eligibility/evaluations/{id}

    Devolve uma execução completa, incluindo os motivos da decisão.
    """

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, evaluation_id):
        evaluation = get_object_or_404(
            EligibilityEvaluation,
            id=evaluation_id,
        )

        return Response(
            EligibilityExecutionSerializer(evaluation).data
        )