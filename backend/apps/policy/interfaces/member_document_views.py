"""Documentos de suporte das pessoas seguras — lado do backoffice (GTE).

Enviar exige poder editar cotações; **analisar** (aprovar/recusar) é uma
decisão de subscrição e exige o mesmo poder que aprovar uma cotação."""
from __future__ import annotations

import uuid

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.client.application import member_document_service
from apps.client.infrastructure.models import InsuredMember, MemberDocument
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.policy.application import member_activation_service
from apps.policy.interfaces.serializers import MemberDocumentReviewSerializer, MemberDocumentUploadSerializer
from shared.pagination import Q360PageNumberPagination


def _actor_ref() -> str:
    actor = CurrentActorProvider.get()
    return actor.actor_id if actor else "unknown"


class MemberDocumentListCreateView(APIView):
    """`GET /members/{memberId}/documents` — documentos enviados e o que ainda falta.
    `POST` — o GTE anexa um documento (recebido em papel, por email…)."""

    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, member_id):
        member = get_object_or_404(InsuredMember, id=member_id)
        return Response(
            {
                "documents": [member_document_service.serialize(d) for d in member_document_service.documents_of(member)],
                "pending": member_activation_service.pending_requirements(member),
            }
        )

    def post(self, request, member_id):
        member = get_object_or_404(InsuredMember, id=member_id)
        body = MemberDocumentUploadSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        metadata = {"unionBondType": data["unionBondType"]} if data.get("unionBondType") else {}
        document = member_document_service.upload_document(
            member=member,
            uploaded_file=data["file"],
            evidence_type=data["evidenceType"],
            note=data["note"],
            metadata=metadata,
            submitted_by_type="STAFF",
            submitted_by_ref=_actor_ref(),
        )
        return Response(member_document_service.serialize(document), status=201)


class MemberDocumentQueueView(APIView):
    """`GET /member-documents` — fila de análise do GTE (por omissão, os que
    aguardam análise)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        status_filter = request.query_params.get("status", "SUBMITTED")
        if status_filter not in ("SUBMITTED", "APPROVED", "REJECTED", "ALL"):
            raise ValidationError({"status": "O estado tem de ser SUBMITTED, APPROVED, REJECTED ou ALL."})
        queryset = MemberDocument.objects.select_related("member").order_by("submitted_at")
        if status_filter != "ALL":
            queryset = queryset.filter(status=status_filter)
        member_id = request.query_params.get("memberId")
        if member_id:
            try:
                queryset = queryset.filter(member_id=uuid.UUID(member_id))
            except ValueError as exc:
                raise ValidationError({"memberId": "Tem de ser um UUID."}) from exc
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        items = [
            {
                **member_document_service.serialize(d),
                "memberName": " ".join(p for p in (d.member.first_name, d.member.last_name) if p) or None,
                "relationshipCode": d.member.relationship_code,
            }
            for d in page
        ]
        return paginator.get_paginated_response(items)


class MemberDocumentDownloadView(APIView):
    """`GET /member-documents/{documentId}/download` — o ficheiro original."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, document_id):
        data, content_type, name = member_document_service.read_file(member_document_service.get_document(document_id))
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{name}"'
        return response


class MemberDocumentReviewView(APIView):
    """`POST /member-documents/{documentId}/review` — aprova ou recusa. Ao aprovar,
    a pessoa é reavaliada: se já cumpre as regras fica elegível na cotação e
    ativa (coberta) na apólice."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, document_id):
        document = member_document_service.get_document(document_id)
        body = MemberDocumentReviewSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        result = member_activation_service.review_document(
            document=document,
            decision=body.validated_data["decision"],
            note=body.validated_data["note"],
            correlation_id=get_correlation_id(),
        )
        return Response(result)
