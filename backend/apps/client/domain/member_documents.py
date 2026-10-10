"""Documentos de suporte de uma pessoa segura (certificado de matrícula, prova
de união, prova de dependência…).

A elegibilidade pode ficar `PENDING_DOCUMENT` por falta de um destes
documentos. Quando o documento é enviado e **aprovado** por um utilizador do
backoffice, passa a contar como evidência e a pessoa é reavaliada: se já
cumpre as regras, fica elegível, coberta e ativa.
"""
from __future__ import annotations

from enum import Enum

MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class EvidenceType(str, Enum):
    ENROLLMENT_CERTIFICATE = "ENROLLMENT_CERTIFICATE"
    UNION_HOMOLOGATION = "UNION_HOMOLOGATION"
    DEPENDENCY_PROOF = "DEPENDENCY_PROOF"
    OTHER = "OTHER"


class DocumentStatus(str, Enum):
    SUBMITTED = "SUBMITTED"  # enviado, a aguardar análise
    APPROVED = "APPROVED"  # aceite: conta como evidência
    REJECTED = "REJECTED"  # recusado: tem de ser enviado outro


EVIDENCE_LABELS = {
    EvidenceType.ENROLLMENT_CERTIFICATE.value: "Certificado de matrícula",
    EvidenceType.UNION_HOMOLOGATION.value: "Comprovativo de união (conservatória ou tribunal)",
    EvidenceType.DEPENDENCY_PROOF.value: "Prova de coabitação ou de dependência financeira",
    EvidenceType.OTHER.value: "Outro documento",
}

# Motivo de pendência da elegibilidade -> documento que o resolve.
REASON_TO_EVIDENCE = {
    "FALTA_CERTIFICADO_MATRICULA": EvidenceType.ENROLLMENT_CERTIFICATE.value,
    "FALTA_HOMOLOGACAO_UNIAO_FACTO": EvidenceType.UNION_HOMOLOGATION.value,
    "FALTA_PROVA_DEPENDENCIA_ASCENDENTE": EvidenceType.DEPENDENCY_PROOF.value,
}

# Documento aprovado -> chave de evidência que a elegibilidade lê (`context.angola`).
EVIDENCE_TO_FLAG = {
    EvidenceType.ENROLLMENT_CERTIFICATE.value: "hasEnrollmentCertificate",
    EvidenceType.UNION_HOMOLOGATION.value: "hasUnionHomologationDocument",
    EvidenceType.DEPENDENCY_PROOF.value: "hasCohabitationOrFinancialDependencyProof",
}


def requirement_for_reason(code: str | None) -> dict | None:
    """O que falta enviar para resolver uma pendência (ou `None` se não for
    uma pendência documental)."""
    evidence = REASON_TO_EVIDENCE.get(code or "")
    if evidence is None:
        return None
    return {"reasonCode": code, "documentType": evidence, "documentLabel": EVIDENCE_LABELS[evidence]}
