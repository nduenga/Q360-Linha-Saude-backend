"""Portal do cliente: enviar os documentos que faltam para uma pessoa segura ficar
coberta (certificado de matrícula do filho, prova de união, prova de
dependência dos pais…) e acompanhar a análise.

O cliente só vê e envia documentos das pessoas seguras dos **seus** clientes
(`_scoped_proposer_ids`). O documento fica «Em análise» até o GTE o aceitar ou
recusar; ao ser aceite a pessoa fica coberta e o cliente é notificado.
"""
from __future__ import annotations

import uuid
from typing import Any

from apps.client.application import member_document_service
from apps.client.domain.errors import InvalidMemberDocumentError
from apps.client.domain.member_documents import DocumentStatus
from apps.client.infrastructure.models import InsuredMember, MemberDocument
from apps.customer_portal.application.self_service import _scoped_proposer_ids
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.foundation.application.context import CurrentActorProvider
from apps.policy.application import member_activation_service

_MAX_WAITING_REVIEW = 10


def _my_member(member_id: uuid.UUID) -> InsuredMember:
    proposer_ids = _scoped_proposer_ids()
    member = InsuredMember.objects.filter(id=member_id, proposer_id__in=proposer_ids).first() if proposer_ids else None
    if member is None:
        raise PortalResourceNotFoundError("Pessoa segura não encontrada")
    return member


def list_my_member_documents(member_id: uuid.UUID) -> dict[str, Any]:
    member = _my_member(member_id)
    return {
        "memberId": str(member.id),
        "documents": [member_document_service.serialize(d) for d in member_document_service.documents_of(member)],
        "pending": member_activation_service.pending_requirements(member),
    }


def upload_my_member_document(
    *, member_id: uuid.UUID, uploaded_file: Any, evidence_type: str, note: str | None, union_bond_type: str | None
) -> dict[str, Any]:
    member = _my_member(member_id)
    waiting = MemberDocument.objects.filter(member=member, status=DocumentStatus.SUBMITTED.value).count()
    if waiting >= _MAX_WAITING_REVIEW:
        raise InvalidMemberDocumentError("Já enviou vários documentos que ainda estão em análise: aguarde a resposta antes de enviar mais")
    actor = CurrentActorProvider.get()
    document = member_document_service.upload_document(
        member=member,
        uploaded_file=uploaded_file,
        evidence_type=evidence_type,
        note=note,
        metadata={"unionBondType": union_bond_type} if union_bond_type else {},
        submitted_by_type="CUSTOMER",
        submitted_by_ref=actor.actor_id if actor else "unknown",
    )
    return member_document_service.serialize(document)
