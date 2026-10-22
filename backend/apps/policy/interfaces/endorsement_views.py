"""Endosso de inclusão (pessoas novas numa apólice ativa, com pro-rata).

  POST /policies/{policyId}/endorsements/inclusions   criar o endosso (cotação ENDORSEMENT)
  GET  /policies/{policyId}/endorsements              endossos aplicados e em curso
  GET  /quotes/{quoteId}/endorsement                  cálculo pro-rata e estado
  PUT  /quotes/{quoteId}/endorsement                  mudar a data de inclusão (antes de submeter)
  POST /quotes/{quoteId}/endorsement/response         resposta do cliente registada pelo GTE

As pessoas juntam-se com `POST /quotes/{id}/members`, o prémio anual calcula-se
com `POST /quotes/{id}/price`, e a submissão e a decisão usam as rotas da
cotação (`/submit`, `/decision`)."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.policy.application import endorsement_service
from apps.quote.infrastructure.models import Quote


class InclusionRequestSerializer(serializers.Serializer):
    inclusionDate = serializers.DateField(help_text="Data de inclusão (não pode ser no passado). É a data de referência do cálculo.")
    memberIds = serializers.ListField(child=serializers.UUIDField(), required=False, default=list,
                                      help_text="Pessoas novas (já registadas no tomador). Podem juntar-se depois.")


class InclusionDateSerializer(serializers.Serializer):
    inclusionDate = serializers.DateField()


class ClientResponseSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["ACCEPT", "REFUSE"])
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None,
                                   help_text="Obrigatório ao recusar (mínimo 10 caracteres).")


def _endorsement(quote_id) -> Quote:
    quote = get_object_or_404(Quote, id=quote_id)
    endorsement_service.require_endorsement(quote)
    return quote


@requires_idempotency
class PolicyInclusionView(APIView):
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CREATE)]

    def post(self, request, policy_id):
        body = InclusionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        quote = endorsement_service.create_inclusion(
            policy_id=policy_id, inclusion_date=body.validated_data["inclusionDate"],
            member_ids=body.validated_data["memberIds"], correlation_id=get_correlation_id(),
        )
        return Response(endorsement_service.describe(quote), status=status.HTTP_201_CREATED)


class PolicyEndorsementListView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        return Response(endorsement_service.list_for_policy(policy_id))


@requires_idempotency
class QuoteEndorsementView(APIView):
    def get_permissions(self):
        if self.request.method == "PUT":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, quote_id):
        return Response(endorsement_service.describe(_endorsement(quote_id)))

    def put(self, request, quote_id):
        body = InclusionDateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        quote = endorsement_service.set_inclusion_date(
            quote=_endorsement(quote_id), inclusion_date=body.validated_data["inclusionDate"],
        )
        return Response(endorsement_service.describe(quote))


@requires_idempotency
class QuoteEndorsementResponseView(APIView):
    """O GTE regista a resposta do cliente (aceitação aplica o endosso à apólice)."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, quote_id):
        body = ClientResponseSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(endorsement_service.respond(
            quote=_endorsement(quote_id), decision=body.validated_data["decision"],
            reason=body.validated_data["reason"], channel="STAFF", correlation_id=get_correlation_id(),
        ))


class QuoteEndorsementDocumentView(APIView):
    """`GET /quotes/{quoteId}/endorsement/document?fileType=pdf|html|docx` —
    proposta de endosso (antes da aceitação) ou ata adicional (depois)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        from django.http import HttpResponse

        from apps.policy.application import policy_document

        data, content_type, name = policy_document.endorsement_document(
            _endorsement(quote_id), request.query_params.get("fileType", "pdf"),
        )
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{name}"'
        return response
