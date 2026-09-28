"""`GET /policies/{policyId}/coverage` and `GET /coverage` — day-to-day
coverage verification (ROADMAP_APOLICES.md Fase 4), distinct from
subscription eligibility (`apps.eligibility`). Read-only, so gated by
`Scope.READ` alone — no `Permission` needed (same posture as
`apps.eligibility`'s own evaluate endpoint, and every other plain read in
this project)."""
from __future__ import annotations

import datetime

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope
from apps.policy.application.coverage_service import get_member_coverage, get_policy_coverage
from apps.policy.domain.coverage import CoverageResult
from apps.policy.infrastructure.models import Policy


def _coverage_payload(result: CoverageResult) -> dict:
    return {
        "covered": result.covered,
        "reasonCode": result.reason_code,
        "message": result.message,
        "waitingPeriodEnds": result.waiting_period_ends.isoformat() if result.waiting_period_ends else None,
    }


def _parse_date(request) -> datetime.date:
    raw = request.query_params.get("date")
    if not raw:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({"date": "Must be an ISO-8601 date (YYYY-MM-DD)."}) from exc


class PolicyCoverageView(APIView):
    """`GET /api/v1/policies/{policyId}/coverage?memberId=&date=&benefitCategory=`
    — `memberId` omitted checks every member on the policy (same
    "omit to check all" posture as `POST /customer-portal/eligibility`)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        on_date = _parse_date(request)
        benefit_category = request.query_params.get("benefitCategory")
        member_id = request.query_params.get("memberId")

        if member_id:
            result = get_member_coverage(policy=policy, member_id=member_id, on_date=on_date, benefit_category=benefit_category)
            return Response({"policyId": str(policy.id), **_coverage_payload(result)})

        results = get_policy_coverage(policy=policy, on_date=on_date, benefit_category=benefit_category)
        return Response(
            {
                "policyId": str(policy.id),
                "results": [{"memberId": r["memberId"], **_coverage_payload(r["result"])} for r in results],
            }
        )


class CoverageLookupView(APIView):
    """`GET /api/v1/coverage?policyNumber=&memberId=&date=&benefitCategory=`
    — the pragmatic lookup-by-number entry point (same posture as
    `GET /quotes?quoteNumber=`), the one an operator/prestador actually
    has in hand instead of a UUID."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        policy_number = request.query_params.get("policyNumber")
        if not policy_number:
            raise ValidationError({"policyNumber": "This query parameter is required."})
        policy = get_object_or_404(Policy, policy_number=policy_number)
        on_date = _parse_date(request)
        benefit_category = request.query_params.get("benefitCategory")
        member_id = request.query_params.get("memberId")

        if member_id:
            result = get_member_coverage(policy=policy, member_id=member_id, on_date=on_date, benefit_category=benefit_category)
            return Response({"policyId": str(policy.id), "policyNumber": policy.policy_number, **_coverage_payload(result)})

        results = get_policy_coverage(policy=policy, on_date=on_date, benefit_category=benefit_category)
        return Response(
            {
                "policyId": str(policy.id),
                "policyNumber": policy.policy_number,
                "results": [{"memberId": r["memberId"], **_coverage_payload(r["result"])} for r in results],
            }
        )
