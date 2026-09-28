"""Authenticated self-service endpoints — ROADMAP_PORTAL_CLIENTE.md
Fase 1, migrated to Policy in Fase 6 (DECISIONS_TAKEN.md#S09-POLICY-001):
"o mínimo útil e seguro: ver que apólice tem, que plano/coberturas
contratou, e se está coberto". All three compose already-existing
application services (`self_service.py`, `benefit_service.py`,
`apps.policy.application.coverage_service`) instead of new domain logic,
scoped to the authenticated customer's own proposers — never to IDs
supplied by the request (Fase 1 task list: "nunca aceitando esses IDs
vindos do pedido do cliente").

`/coverage` (GET) and `/eligibility` (POST) both now answer "am I
covered?" via `apps.policy.domain.coverage.check_coverage` — the
day-to-day coverage question a customer actually has, not the
subscription-time question `apps.eligibility` answers (that one is only
ever relevant before a Policy exists). Kept as two endpoints (not
collapsed into one) only to avoid a breaking URL/method change on top of
the already-breaking policyNumber migration.
"""
from __future__ import annotations

import datetime

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application.self_service import list_my_policies, resolve_my_policy
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.interfaces.authentication import CustomerPortalJwtAuthentication
from apps.customer_portal.interfaces.permissions import IsCustomerPortalActor
from apps.customer_portal.interfaces.self_service_serializers import CustomerPortalCoverageRequestSerializer
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.policy.application.coverage_service import get_member_coverage, get_policy_coverage
from apps.policy.domain.coverage import CoverageResult
from apps.policy.infrastructure.models import PolicyMember, PremiumInstallment
from apps.policy.interfaces.serializers import PolicySerializer
from apps.pricing.domain.money import round_amount
from apps.product.application.benefit_service import list_plan_benefits
from apps.product.infrastructure.models import Plan
from apps.product.interfaces.serializers import PlanBenefitSerializer, PlanSerializer, ProductSerializer


def _outstanding_installments_by_policy(policies: list) -> dict:
    """ROADMAP_APOLICES.md Fase 6 ("`/me` lista apólices e o seu estado,
    incluindo recibos em dívida"): `DUE`/`OVERDUE` installments, grouped
    per policy — just a count and total, not the installments themselves
    (a customer needs to know "do I owe something", not a ledger)."""
    if not policies:
        return {}
    installments = PremiumInstallment.objects.filter(
        policy_id__in=[p.id for p in policies], status__in=["DUE", "OVERDUE"]
    )
    totals: dict = {}
    for installment in installments:
        entry = totals.setdefault(installment.policy_id, {"count": 0, "totalAmount": 0})
        entry["count"] += 1
        entry["totalAmount"] += installment.amount
    return {
        policy_id: {"count": v["count"], "totalAmount": str(round_amount(v["totalAmount"]))}
        for policy_id, v in totals.items()
    }


def _coverage_payload(result: CoverageResult) -> dict:
    return {
        "covered": result.covered,
        "reasonCode": result.reason_code,
        "message": result.message,
        "waitingPeriodEnds": result.waiting_period_ends.isoformat() if result.waiting_period_ends else None,
    }


class CustomerPortalMeView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]

    def get(self, request):
        policies = list(list_my_policies())
        plans = {p.id: p for p in Plan.objects.select_related("product").filter(id__in=[p.plan_id for p in policies])}
        outstanding_by_policy = _outstanding_installments_by_policy(policies)

        items = []
        for policy in policies:
            plan = plans.get(policy.plan_id)
            items.append(
                {
                    "policy": PolicySerializer(policy).data,
                    "product": ProductSerializer(plan.product).data if plan else None,
                    "plan": PlanSerializer(plan).data if plan else None,
                    "outstandingInstallments": outstanding_by_policy.get(policy.id, {"count": 0, "totalAmount": "0.00"}),
                }
            )
        return Response({"policies": items}, status=200)


class CustomerPortalCoverageView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]

    def get(self, request):
        policy_number = request.query_params.get("policyNumber")
        if not policy_number:
            raise ValidationError({"policyNumber": "This query parameter is required."})

        policy = resolve_my_policy(policy_number)
        member_id = request.query_params.get("memberId")
        raw_date = request.query_params.get("date")
        on_date = _parse_date(raw_date)
        benefit_category = request.query_params.get("benefitCategory")

        if member_id:
            _assert_member_belongs_to_policy(policy=policy, member_id=member_id)
            result = get_member_coverage(policy=policy, member_id=member_id, on_date=on_date, benefit_category=benefit_category)
            return Response({"policyNumber": policy.policy_number, "memberId": member_id, **_coverage_payload(result)})

        results = get_policy_coverage(policy=policy, on_date=on_date, benefit_category=benefit_category)
        return Response(
            {
                "policyNumber": policy.policy_number,
                "results": [{"memberId": r["memberId"], **_coverage_payload(r["result"])} for r in results],
            }
        )


class CustomerPortalPlanBenefitsView(APIView):
    """`GET /customer-portal/plan-benefits?policyNumber=` — the catalogue
    of contracted coverages (what `/coverage` used to return before Fase
    6 repurposed that path for the actual coverage check). Reaproveita
    `list_plan_benefits` sem alteração nenhuma, tal como na Fase 1
    original."""

    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]

    def get(self, request):
        policy_number = request.query_params.get("policyNumber")
        if not policy_number:
            raise ValidationError({"policyNumber": "This query parameter is required."})

        policy = resolve_my_policy(policy_number)
        plan = Plan.objects.filter(id=policy.plan_id).first()
        if plan is None:
            raise PortalResourceNotFoundError("No plan found for this policy")

        benefits = list_plan_benefits(plan=plan)
        return Response(
            {"policyNumber": policy.policy_number, "benefits": PlanBenefitSerializer(benefits, many=True).data},
            status=200,
        )


@requires_idempotency
class CustomerPortalEligibilityView(APIView):
    """`POST /customer-portal/eligibility` — same coverage check as `GET
    /coverage`, as a POST with a body (kept for URL/method
    backward-compatibility with Fase 1; see module docstring)."""

    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]

    def post(self, request):
        body = CustomerPortalCoverageRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        policy = resolve_my_policy(data["policyNumber"])
        on_date = data["date"] or datetime.date.today()
        member_id = data.get("memberId")

        if member_id is not None:
            _assert_member_belongs_to_policy(policy=policy, member_id=member_id)
            result = get_member_coverage(
                policy=policy, member_id=member_id, on_date=on_date, benefit_category=data["benefitCategory"]
            )
            results = [{"memberId": str(member_id), "result": result}]
        else:
            results = get_policy_coverage(policy=policy, on_date=on_date, benefit_category=data["benefitCategory"])

        return Response(
            {
                "policyNumber": policy.policy_number,
                "results": [{"memberId": r["memberId"], **_coverage_payload(r["result"])} for r in results],
            },
            status=200,
        )


def _parse_date(raw: str | None) -> datetime.date:
    if not raw:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({"date": "Must be an ISO-8601 date (YYYY-MM-DD)."}) from exc


def _assert_member_belongs_to_policy(*, policy, member_id) -> None:
    if not PolicyMember.objects.filter(policy=policy, member_id=member_id).exists():
        raise PortalResourceNotFoundError("No such member on this policy")
