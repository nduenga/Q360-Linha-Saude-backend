"""Questionário clínico no Portal: só o que a seguradora pediu ao cliente, e
só nas cotações das contas a que o cliente está ligado."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application.portal_read import my_visible_quotes
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.interfaces.authentication import CustomerPortalJwtAuthentication
from apps.customer_portal.interfaces.permissions import IsCustomerPortalActor
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.quote.application import questionnaire_service
from apps.quote.infrastructure.models import ClinicalQuestionnaire
from apps.quote.interfaces.workflow_views import (
    QuestionnaireCompleteRequestSerializer,
    QuestionnaireSaveRequestSerializer,
)


class _PortalView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]


def _requested_quote(quote_number: str, member_id):
    quote = my_visible_quotes().filter(quote_number=quote_number).first()
    requested = quote is not None and ClinicalQuestionnaire.objects.filter(
        quote=quote, member_id=member_id, requested_from_customer_at__isnull=False
    ).exists()
    if not requested:
        raise PortalResourceNotFoundError("Não foi encontrado nenhum questionário pedido para esta pessoa")
    return quote


class CustomerPortalQuestionnaireListView(_PortalView):
    def get(self, request):
        return Response({"items": questionnaire_service.pending_for_customer(my_visible_quotes())})


class CustomerPortalQuestionnaireView(_PortalView):
    def get(self, request, quote_number, member_id):
        return Response(questionnaire_service.detail(_requested_quote(quote_number, member_id), member_id))

    def put(self, request, quote_number, member_id):
        quote = _requested_quote(quote_number, member_id)
        body = QuestionnaireSaveRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(questionnaire_service.save(
            quote=quote, member_id=member_id, answers=data["answers"], current_section=data["currentSection"],
            row_version=data["rowVersion"], channel=questionnaire_service.CUSTOMER,
        ))


@requires_idempotency
class CustomerPortalQuestionnaireCompleteView(_PortalView):
    def post(self, request, quote_number, member_id):
        quote = _requested_quote(quote_number, member_id)
        body = QuestionnaireCompleteRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(questionnaire_service.complete(
            quote=quote, member_id=member_id, row_version=body.validated_data["rowVersion"],
            channel=questionnaire_service.CUSTOMER,
        ))
