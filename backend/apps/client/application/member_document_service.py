"""Envio e consulta de documentos de suporte das pessoas seguras.

Quem pode enviar: o backoffice (GTE) e o próprio cliente no portal. Um
documento enviado fica `SUBMITTED`; só conta como evidência de elegibilidade
depois de **aprovado** por um utilizador do backoffice (a análise e a
reavaliação da pessoa vivem em `apps.policy.application.member_activation_service`).
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.client.domain.errors import InvalidMemberDocumentError, MemberDocumentNotFoundError
from apps.client.domain.member_documents import (
    ALLOWED_CONTENT_TYPES,
    EVIDENCE_LABELS,
    EVIDENCE_TO_FLAG,
    MAX_FILE_BYTES,
    DocumentStatus,
    EvidenceType,
)
from apps.client.infrastructure.models import InsuredMember, MemberDocument
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def upload_document(
    *,
    member: InsuredMember,
    uploaded_file: Any,
    evidence_type: str,
    note: str | None,
    metadata: dict | None,
    submitted_by_type: str,
    submitted_by_ref: str,
) -> MemberDocument:
    if evidence_type not in EVIDENCE_LABELS:
        raise InvalidMemberDocumentError(f"O tipo de documento (evidenceType) tem de ser um de {sorted(EVIDENCE_LABELS)}")
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidMemberDocumentError("Formato de ficheiro não suportado: envie um PDF, JPG ou PNG")
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size <= 0:
        raise InvalidMemberDocumentError("O ficheiro está vazio")
    if size > MAX_FILE_BYTES:
        raise InvalidMemberDocumentError(f"O ficheiro excede o tamanho máximo de {MAX_FILE_BYTES // (1024 * 1024)} MB")

    tenant_id = CurrentTenantProvider.require().value
    document_id = uuid.uuid4()
    relative = Path("member-documents") / str(tenant_id) / str(member.id) / f"{document_id}{ALLOWED_CONTENT_TYPES[content_type]}"
    target = Path(settings.MEDIA_ROOT) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with target.open("wb") as out:
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
            out.write(chunk)

    document = MemberDocument.objects.create(
        id=document_id,
        tenant_id=tenant_id,
        member=member,
        evidence_type=evidence_type,
        status=DocumentStatus.SUBMITTED.value,
        original_filename=(getattr(uploaded_file, "name", None) or "documento")[:255],
        content_type=content_type,
        size_bytes=size,
        checksum=digest.hexdigest(),
        storage_key=str(relative),
        metadata_json=metadata or {},
        note=(note or "").strip() or None,
        submitted_by_type=submitted_by_type,
        submitted_by_ref=submitted_by_ref[:200],
    )
    _audit.record(
        action="member_document.submitted",
        entity_type="MemberDocument",
        entity_id=str(document.id),
        metadata={"memberId": str(member.id), "evidenceType": evidence_type, "by": submitted_by_type},
    )
    _outbox.append(
        aggregate_type="MemberDocument",
        aggregate_id=str(document.id),
        event_type="MEMBER.DOCUMENT.SUBMITTED",
        payload={"documentId": str(document.id), "memberId": str(member.id), "evidenceType": evidence_type},
    )
    return document


def documents_of(member: InsuredMember):
    return MemberDocument.objects.filter(member=member).order_by("-submitted_at")


def get_document(document_id: uuid.UUID) -> MemberDocument:
    document = MemberDocument.objects.select_related("member").filter(id=document_id).first()
    if document is None:
        raise MemberDocumentNotFoundError("Documento não encontrado")
    return document


def read_file(document: MemberDocument) -> tuple[bytes, str, str]:
    path = Path(settings.MEDIA_ROOT) / document.storage_key
    if not path.exists():
        raise MemberDocumentNotFoundError("O ficheiro do documento já não está disponível")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != document.checksum:
        raise MemberDocumentNotFoundError("O ficheiro do documento falhou a verificação de integridade")
    return data, document.content_type, document.original_filename


def evidence_for(member: InsuredMember) -> dict[str, Any]:
    """Evidência que os documentos **aprovados** da pessoa dão à elegibilidade
    (`context.angola`). Só acrescenta `True`: nunca retira evidência dada por quem
    chama."""
    evidence: dict[str, Any] = {}
    approved = MemberDocument.objects.filter(member=member, status=DocumentStatus.APPROVED.value).order_by("submitted_at")
    for document in approved:
        flag = EVIDENCE_TO_FLAG.get(document.evidence_type)
        if flag:
            evidence[flag] = True
        if document.evidence_type == EvidenceType.UNION_HOMOLOGATION.value and document.metadata_json.get("unionBondType"):
            evidence["unionBondType"] = document.metadata_json["unionBondType"]
    bond = (member.attributes_json or {}).get("unionBondType")
    if bond and "unionBondType" not in evidence:
        evidence["unionBondType"] = bond
    return evidence


def serialize(document: MemberDocument) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "memberId": str(document.member_id),
        "evidenceType": document.evidence_type,
        "evidenceLabel": EVIDENCE_LABELS.get(document.evidence_type, document.evidence_type),
        "status": document.status,
        "statusLabel": {"SUBMITTED": "Em análise", "APPROVED": "Aceite", "REJECTED": "Recusado"}.get(document.status, document.status),
        "fileName": document.original_filename,
        "contentType": document.content_type,
        "sizeBytes": document.size_bytes,
        "note": document.note,
        "submittedBy": document.submitted_by_type,
        "submittedAt": document.submitted_at,
        "reviewedAt": document.reviewed_at,
        "reviewNote": document.review_note,
    }
