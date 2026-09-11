"""ART-006 `/api/v1/eligibility/evaluate`: `evaluateEligibility` (POST),
security -> oauth2: [q360.write]. No DOC-001 s18 permission gates this
domain (not in the matrix), same as the client module."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.eligibility.interfaces.serializers import EligibilityRequestSerializer, EligibilityResponseSerializer
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.foundation.interfaces.permissions import require_scope


class EligibilityEvaluateView(APIView):
    permission_classes = [require_scope(Scope.WRITE)]

    def post(self, request):
        body = EligibilityRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        evaluation = EvaluateEligibilityUseCase().execute(
            proposer_id=data["proposerId"],
            member_id=data["memberId"],
            product_version_id=data["productVersionId"],
            plan_id=data["planId"],
            effective_date=data["effectiveDate"],
            context=data["context"],
            correlation_id=get_correlation_id(),
        )
        return Response(EligibilityResponseSerializer(evaluation).data, status=200)
