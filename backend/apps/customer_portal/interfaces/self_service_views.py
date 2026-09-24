"""Authenticated self-service endpoints — ROADMAP_PORTAL_CLIENTE.md
Fase 1: "o mínimo útil e seguro: ver que apólice tem, que plano/
coberturas contratou, e se está elegível". All three compose already-
existing application services (`self_service.py`, `benefit_service.py`,
`EvaluateEligibilityUseCase`) instead of new domain logic, scoped to the
authenticated customer's own proposers — never to IDs supplied by the
request (Fase 1 task list: "nunca aceitando esses IDs vindos do pedido
do cliente").
"""
from __future__ import annotations

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application.self_service import list_my_quotes, resolve_my_quote
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.interfaces.authentication import CustomerPortalJwtAuthentication
from apps.customer_portal.interfaces.permissions import IsCustomerPortalActor
from apps.customer_portal.interfaces.self_service_serializers import (
    CustomerPortalEligibilityRequestSerializer,
)
from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.product.application.benefit_service import list_plan_benefits
from apps.product.interfaces.serializers import (
    PlanBenefitSerializer,
    PlanSerializer,
    ProductSerializer,
    ProductVersionSerializer,
)
from apps.product.infrastructure.models import Plan, ProductVersion
from apps.quote.infrastructure.models import QuoteMember
from apps.quote.interfaces.serializers import QuoteSerializer


class CustomerPortalMeView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]

    def get(self, request):
        quotes = list_my_quotes()
        product_versions = {
            pv.id: pv
            for pv in ProductVersion.objects.select_related("product").filter(
                id__in=[q.product_version_id for q in quotes]
            )
        }
        plans = {p.id: p for p in Plan.objects.filter(id__in=[q.plan_id for q in quotes])}

        items = []
        for quote in quotes:
            product_version = product_versions.get(quote.product_version_id)
            plan = plans.get(quote.plan_id)
            items.append(
                {
                    "quote": QuoteSerializer(quote).data,
                    "product": ProductSerializer(product_version.product).data if product_version else None,
                    "productVersion": ProductVersionSerializer(product_version).data if product_version else None,
                    "plan": PlanSerializer(plan).data if plan else None,
                }
            )
        return Response({"quotes": items}, status=200)


class CustomerPortalCoverageView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]

    def get(self, request):
        quote_number = request.query_params.get("quoteNumber")
        if not quote_number:
            raise ValidationError({"quoteNumber": "This query parameter is required."})

        quote = resolve_my_quote(quote_number)
        plan = Plan.objects.filter(id=quote.plan_id).first()
        if plan is None:
            raise PortalResourceNotFoundError("No plan found for this policy")

        benefits = list_plan_benefits(plan=plan)
        return Response(
            {"quoteNumber": quote.quote_number, "benefits": PlanBenefitSerializer(benefits, many=True).data},
            status=200,
        )


@requires_idempotency
class CustomerPortalEligibilityView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]

    def post(self, request):
        body = CustomerPortalEligibilityRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        quote = resolve_my_quote(data["quoteNumber"])
        quote_members = QuoteMember.objects.filter(quote=quote).select_related("member")
        member_id = data.get("memberId")
        if member_id is not None:
            quote_members = quote_members.filter(member_id=member_id)
            if not quote_members.exists():
                raise PortalResourceNotFoundError("No such member on this policy")

        results = []
        for quote_member in quote_members:
            evaluation = EvaluateEligibilityUseCase().execute(
                proposer_id=quote.proposer_id,
                member_id=quote_member.member_id,
                product_version_id=quote.product_version_id,
                plan_id=quote.plan_id,
                effective_date=quote.effective_date,
                context={},
                correlation_id=get_correlation_id(),
            )
            results.append(
                {
                    "memberId": str(quote_member.member_id),
                    "relationshipCode": quote_member.member.relationship_code if quote_member.member else None,
                    "decision": evaluation.decision,
                    "messages": evaluation.evidence_json,
                }
            )

        return Response({"quoteNumber": quote.quote_number, "results": results}, status=200)
