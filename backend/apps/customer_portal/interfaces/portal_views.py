"""Read-only Portal Cliente endpoints beyond `/me` (Portal_Cliente_Sistema_
Cotacoes_Saude.pdf, MVP). Same authentication/scoping as `self_service_views`;
the logic lives in `apps.customer_portal.application.portal_read`."""
from __future__ import annotations

import uuid

from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application import portal_read
from apps.customer_portal.infrastructure.models import CustomerAccount
from apps.customer_portal.interfaces.authentication import CustomerPortalJwtAuthentication
from apps.customer_portal.interfaces.permissions import IsCustomerPortalActor
from apps.foundation.application.context import CurrentActorProvider

_PHASES = {"ACTIVE", "EXPIRING", "RENEWED", "EXPIRED", "CANCELLED", "OTHER"}
_INSTALLMENT_STATUSES = {"DUE", "PAID", "OVERDUE"}


class _PortalView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]


class CustomerPortalDashboardView(_PortalView):
    def get(self, request):
        return Response(portal_read.get_my_dashboard())


class CustomerPortalQuoteDetailView(_PortalView):
    def get(self, request, quote_number: str):
        return Response(portal_read.get_my_quote(quote_number))


class CustomerPortalPolicyListView(_PortalView):
    def get(self, request):
        phase = request.query_params.get("phase")
        if phase and phase not in _PHASES:
            raise ValidationError({"phase": f"Must be one of {sorted(_PHASES)}."})
        return Response({"policies": portal_read.list_my_policies_summary(phase=phase)})


class CustomerPortalPolicyDetailView(_PortalView):
    def get(self, request, policy_number: str):
        return Response(portal_read.get_my_policy(policy_number))


def _file(data: bytes, content_type: str, name: str) -> HttpResponse:
    response = HttpResponse(data, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


class CustomerPortalPolicyDocumentView(_PortalView):
    """A apólice digital."""

    def get(self, request, policy_number: str):
        return _file(*portal_read.my_policy_document(policy_number, request.query_params.get("fileType", "pdf")))


class CustomerPortalPolicyStatementView(_PortalView):
    """Declaração de cobertura (`kind=COVERAGE`) ou comprovativo de pagamento
    (`kind=PAYMENT`, opcional `installmentNo`), gerados na hora — sem pedido."""

    def get(self, request, policy_number: str):
        kind = request.query_params.get("kind", "COVERAGE").upper()
        if kind not in ("COVERAGE", "PAYMENT"):
            raise ValidationError({"kind": "Must be COVERAGE or PAYMENT."})
        raw = request.query_params.get("installmentNo")
        try:
            installment_no = int(raw) if raw else None
        except ValueError as exc:
            raise ValidationError({"installmentNo": "Must be an integer."}) from exc
        return _file(*portal_read.my_policy_statement(policy_number, kind=kind, installment_no=installment_no))


class CustomerPortalPolicyHistoryView(_PortalView):
    def get(self, request, policy_number: str):
        return Response({"policyNumber": policy_number, "events": portal_read.list_my_state_history(policy_number)})


class CustomerPortalCardView(_PortalView):
    def get(self, request, policy_number: str, member_id: uuid.UUID):
        return Response(portal_read.get_my_card(policy_number, member_id))


class CustomerPortalBeneficiariesView(_PortalView):
    def get(self, request):
        return Response({"beneficiaries": portal_read.list_my_beneficiaries()})


class CustomerPortalPaymentsView(_PortalView):
    def get(self, request):
        status = request.query_params.get("status")
        if status and status not in _INSTALLMENT_STATUSES:
            raise ValidationError({"status": f"Must be one of {sorted(_INSTALLMENT_STATUSES)}."})
        return Response(portal_read.list_my_payments(status=status))


class CustomerPortalDocumentsView(_PortalView):
    def get(self, request):
        return Response({"documents": portal_read.list_my_documents()})


class CustomerPortalDocumentDownloadView(_PortalView):
    def get(self, request, document_id: uuid.UUID):
        data, content_type, name = portal_read.open_my_document(document_id)
        response = HttpResponse(data, content_type=content_type)
        if name:
            response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response


class CustomerPortalProfileView(_PortalView):
    def get(self, request):
        actor = CurrentActorProvider.get()
        account = CustomerAccount.objects.filter(id=actor.actor_id).first() if actor else None
        return Response(portal_read.get_my_profile(account_email=account.email if account else None))
