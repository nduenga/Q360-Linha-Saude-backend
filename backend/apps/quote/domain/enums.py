"""ART-005 `ck_quote_status`/`ck_quote_member_status`/`ck_quote_snapshot_type`
(ART-012 V019/V020); ART-006 `Quote.status`; ART-009 "Quote Machine" sheet.
Do not add a value not in both.
"""
from __future__ import annotations

from enum import Enum


class QuoteStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    # DECISIONS_TAKEN.md#S09-POLICY-001 (ROADMAP_APOLICES.md Fase 2):
    # deliberate deviation from ART-005/ART-009 (neither declares this
    # value) — a Quote that has produced a Policy (apps.policy) is
    # terminal, distinct from APPROVED, so it can never be signed twice
    # nor expire out from under an already-issued contract. See
    # apps/quote/infrastructure/migrations/0005_bound_status.py.
    BOUND = "BOUND"


# Mesmos rótulos do frontend (src/components/Statusbadge.tsx, "nomenclatura
# consistente em toda a aplicação (regra 16.1)") — usados nas mensagens de
# erro para a pessoa ver "Cancelada (CANCELLED)" em vez do código cru.
QUOTE_STATUS_LABEL: dict[str, str] = {
    QuoteStatus.DRAFT.value: "Rascunho",
    QuoteStatus.READY.value: "Calculada",
    QuoteStatus.IN_REVIEW.value: "Em Revisão",
    QuoteStatus.APPROVED.value: "Aprovada",
    QuoteStatus.REJECTED.value: "Rejeitada",
    QuoteStatus.EXPIRED.value: "Expirada",
    QuoteStatus.CANCELLED.value: "Cancelada",
    QuoteStatus.BOUND.value: "Emitida",
}


def quote_status_label(status: str) -> str:
    """'CANCELLED' -> 'Cancelada (CANCELLED)'; mantém o código técnico entre
    parêntesis porque é o que a equipa de suporte/engenharia reconhece nos
    logs e no ART-009, a par do nome que a pessoa a decidir entende."""
    label = QUOTE_STATUS_LABEL.get(status)
    return f"{label} ({status})" if label else status


class QuoteMemberStatus(str, Enum):
    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"
    REFERRAL = "REFERRAL"


class QuoteSnapshotType(str, Enum):
    PRICING = "PRICING"
    SUBMISSION = "SUBMISSION"
    APPROVAL = "APPROVAL"
    DOCUMENT = "DOCUMENT"


class ReviewTaskStatus(str, Enum):
    """ART-005 `ck_review_status` (ART-012 V022); ART-006 `ReviewTask.status`;
    ART-009 "Review Machine" sheet."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DECIDED = "DECIDED"
    RETURNED = "RETURNED"


class QuoteDecisionType(str, Enum):
    """ART-005 `ck_quote_decision` (ART-012 V023); ART-006 `DecisionRequest.decision`."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RETURN = "RETURN"


class DocumentTemplateStatus(str, Enum):
    """ART-005 `ck_template_status` (ART-012 V024)."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class DocumentType(str, Enum):
    """ART-005 `ck_document_type` (ART-012 V024); ART-006 `Document.documentType`
    (currently a single fixed `const`)."""

    QUOTE_PROPOSAL = "QUOTE_PROPOSAL"


class DocumentStatus(str, Enum):
    """ART-005 `ck_document_status` (ART-012 V024); ART-006 `Document.status`;
    ART-009 "Document" row in the State Catalogue."""

    REQUESTED = "REQUESTED"
    GENERATED = "GENERATED"
    FAILED = "FAILED"
