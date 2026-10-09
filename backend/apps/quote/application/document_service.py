"""Document generation (Q360-S8-01).

OPEN DECISION — see DECISIONS_TAKEN.md#S08-DOCUMENT-001: OD-006 ("template
oficial da proposta") is genuinely unresolved, and ART-006 has no
create/publish endpoint for `DocumentTemplateVersion` at all (unlike
RatingTable/PricingParameterSet/RuleVersion, whose configType is a CLOSED
enum on the shared publish endpoint that a 4th value would silently
violate) — so this module adds its own dedicated, pragmatic
create/publish endpoints for it, and "generation" produces a clearly
labeled placeholder artifact (a JSON summary of the approved snapshot),
never a real branded/legal PDF. This proves the whole mechanism
end-to-end (numbering, checksum, immutability, reproducibility) without
inventing OD-006's actual content.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.quote.application.numbering_service import next_continuous_value
from apps.quote.domain.enums import DocumentStatus, DocumentTemplateStatus, DocumentType, QuoteSnapshotType, QuoteStatus
from apps.quote.domain.errors import QuoteStateError
from apps.quote.domain.proposal_template import validate_template_body
from apps.quote.infrastructure.models import Document, DocumentTemplateVersion, Quote, QuoteSnapshot

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


class DuplicateTemplateCodeError(QuoteStateError):
    http_status = 409
    problem_code = "CONFLICT"


class TemplateImmutableError(QuoteStateError):
    http_status = 409
    problem_code = "CONFLICT"


class TemplateNotFoundError(QuoteStateError):
    http_status = 404
    problem_code = "NOT-FOUND"


def create_document_template(
    *, template_code: str, storage_ref: str, effective_from, effective_to=None
) -> DocumentTemplateVersion:
    tenant_id = CurrentTenantProvider.require()
    validate_template_body(storage_ref)
    checksum = hashlib.sha256(storage_ref.encode("utf-8")).hexdigest()
    try:
        with transaction.atomic():
            next_version_no = (
                DocumentTemplateVersion.objects.filter(template_code=template_code)
                .order_by("-version_no")
                .values_list("version_no", flat=True)
                .first()
                or 0
            ) + 1
            template = DocumentTemplateVersion.objects.create(
                tenant_id=tenant_id.value,
                template_code=template_code,
                version_no=next_version_no,
                storage_ref=storage_ref,
                checksum=checksum,
                effective_from=effective_from,
                effective_to=effective_to,
            )
    except IntegrityError as exc:
        raise DuplicateTemplateCodeError(f"Já existe a versão deste modelo de documento '{template_code}'") from exc

    _audit.record(action="document_template.created", entity_type="DocumentTemplateVersion", entity_id=str(template.id))
    return template


def publish_document_template(template: DocumentTemplateVersion) -> DocumentTemplateVersion:
    actor = CurrentActorProvider.get()
    updated = DocumentTemplateVersion.objects.filter(id=template.id, status=DocumentTemplateStatus.DRAFT.value).update(
        status=DocumentTemplateStatus.PUBLISHED.value, published_at=timezone.now(), published_by=actor.actor_id if actor else None
    )
    if updated == 0:
        raise TemplateImmutableError(f"O modelo de documento {template.id} não está em rascunho (DRAFT); só um rascunho pode ser publicado")
    template.refresh_from_db()
    _audit.record(action="document_template.published", entity_type="DocumentTemplateVersion", entity_id=str(template.id))
    return template


def update_document_template(
    template: DocumentTemplateVersion, *, storage_ref: str
) -> DocumentTemplateVersion:
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6: only a DRAFT template can
    be edited."""
    validate_template_body(storage_ref)
    checksum = hashlib.sha256(storage_ref.encode("utf-8")).hexdigest()
    updated = DocumentTemplateVersion.objects.filter(
        id=template.id, status=DocumentTemplateStatus.DRAFT.value
    ).update(storage_ref=storage_ref, checksum=checksum)
    if updated == 0:
        raise TemplateImmutableError(
            f"O modelo de documento {template.id} não está em rascunho (DRAFT); só um rascunho pode ser editado"
        )
    template.refresh_from_db()
    _audit.record(action="document_template.updated", entity_type="DocumentTemplateVersion", entity_id=str(template.id))
    return template


def delete_document_template(template: DocumentTemplateVersion) -> None:
    """Only a DRAFT template can be deleted."""
    deleted, _ = DocumentTemplateVersion.objects.filter(
        id=template.id, status=DocumentTemplateStatus.DRAFT.value
    ).delete()
    if deleted == 0:
        raise TemplateImmutableError(
            f"O modelo de documento {template.id} não está em rascunho (DRAFT); só um rascunho pode ser eliminado"
        )
    _audit.record(action="document_template.deleted", entity_type="DocumentTemplateVersion", entity_id=str(template.id))


def retire_document_template(template: DocumentTemplateVersion) -> DocumentTemplateVersion:
    """OD-ANGOLA-006: "remover" on something PUBLISHED means retire, not
    delete -- a Document already generated from this template must keep
    resolving it."""
    updated = DocumentTemplateVersion.objects.filter(
        id=template.id, status=DocumentTemplateStatus.PUBLISHED.value
    ).update(status=DocumentTemplateStatus.RETIRED.value)
    if updated == 0:
        raise TemplateImmutableError(
            f"O modelo de documento {template.id} não está publicado (PUBLISHED); só um modelo publicado pode ser retirado"
        )
    template.refresh_from_db()
    _audit.record(action="document_template.retired", entity_type="DocumentTemplateVersion", entity_id=str(template.id))
    return template


def _resolve_published_template(*, template_code: str, effective_date) -> DocumentTemplateVersion | None:
    from django.db.models import Q

    return (
        DocumentTemplateVersion.objects.filter(
            template_code=template_code, status=DocumentTemplateStatus.PUBLISHED.value, effective_from__lte=effective_date
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )


def resolve_template_for(*, template_code: str, effective_date) -> DocumentTemplateVersion | None:
    """Modelo publicado em vigor para gerar um documento.

    Um documento é emitido agora, por isso o modelo que conta é o que está em
    vigor **hoje**; só se não houver, tenta-se o que vigora na data de início
    da cotação. (Antes só se olhava para a data de início da cotação, e um
    modelo criado hoje só servia para cotações a começar nesse dia.)"""
    for day in (timezone.now().date(), effective_date):
        template = _resolve_published_template(template_code=template_code, effective_date=day)
        if template is not None:
            return template
    return None


def template_not_found_message(*, template_code: str, effective_date) -> str:
    published = list(
        DocumentTemplateVersion.objects.filter(template_code=template_code, status=DocumentTemplateStatus.PUBLISHED.value)
        .order_by("effective_from", "version_no")
    )
    if not published:
        detail = "Não há nenhuma versão publicada deste modelo: crie-a e publique-a em «Modelos de documento»."
    else:
        periods = "; ".join(
            f"v{t.version_no}: de {t.effective_from} " + (f"a {t.effective_to}" if t.effective_to else "sem data de fim")
            for t in published
        )
        detail = f"Versões publicadas e respetivos períodos de vigência: {periods}."
    return (
        f"Não há nenhum modelo de documento '{template_code}' em vigor hoje ({timezone.now().date()}) "
        f"nem na data de início da cotação ({effective_date}). {detail}"
    )


# OD-006 placeholder: no approved document names a real template code, so
# this is this module's own fixed convention (mirrors S04-PRICING-CONTEXT-001's
# BASE_PREMIUM parameter code convention) - an Admin must create+publish a
# DocumentTemplateVersion with exactly this code before any proposal can be
# generated (fails closed with NOT-FOUND otherwise, same fail-safe posture
# as the pricing engine's missing-config path).
DEFAULT_TEMPLATE_CODE = "QUOTE_PROPOSAL_DEFAULT"


def generate_quote_proposal(*, quote: Quote) -> Document:
    if quote.status != QuoteStatus.APPROVED.value:
        raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; só se pode gerar a proposta depois de a cotação estar aprovada (APPROVED)")

    approval_snapshot = (
        QuoteSnapshot.objects.filter(quote=quote, snapshot_type=QuoteSnapshotType.APPROVAL.value)
        .order_by("-snapshot_no")
        .first()
    )
    if approval_snapshot is None:
        raise QuoteStateError(f"A cotação {quote.id} não tem registo de aprovação (snapshot) para gerar a proposta")

    template = resolve_template_for(template_code=DEFAULT_TEMPLATE_CODE, effective_date=quote.effective_date)
    if template is None:
        raise TemplateNotFoundError(
template_not_found_message(template_code=DEFAULT_TEMPLATE_CODE, effective_date=quote.effective_date)
        )

    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    tenant_id = CurrentTenantProvider.require()

    document = Document.objects.create(
        tenant_id=tenant_id.value,
        quote=quote,
        snapshot=approval_snapshot,
        template_version=template,
        document_type=DocumentType.QUOTE_PROPOSAL.value,
        status=DocumentStatus.REQUESTED.value,
        requested_by=actor_id,
    )

    _outbox.append(
        aggregate_type="Document",
        aggregate_id=str(document.id),
        event_type="DOCUMENT.GENERATION.REQUESTED",
        payload={
            "documentId": str(document.id),
            "quoteId": str(quote.id),
            "documentType": DocumentType.QUOTE_PROPOSAL.value,
            "requestedBy": actor_id,
        },
    )

    try:
        payload = {
            "documentId": str(document.id),
            "quoteId": str(quote.id),
            "templateCode": template.template_code,
            "templateVersion": template.version_no,
            "snapshotNo": approval_snapshot.snapshot_no,
            "snapshot": approval_snapshot.snapshot_json,
            "note": "OD-006 placeholder artifact - not an official branded/legal proposal document.",
        }
        content = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
        checksum = hashlib.sha256(content).hexdigest()

        documents_dir = Path(settings.MEDIA_ROOT) / "documents"
        documents_dir.mkdir(parents=True, exist_ok=True)
        file_path = documents_dir / f"{document.id}.json"
        file_path.write_bytes(content)

        document_number = next_continuous_value(sequence_code="QUOTE_PROPOSAL")

        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.GENERATED.value,
            storage_ref=str(file_path),
            checksum=checksum,
            document_number=document_number,
            generated_at=timezone.now(),
        )
        document.refresh_from_db()
    except Exception as exc:
        failure_str = str(exc)[:100]
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.FAILED.value,
            failure_code=failure_str,
            generated_at=timezone.now(),
        )
        document.refresh_from_db()
        _audit.record(
            action="document.generation_failed",
            entity_type="Document",
            entity_id=str(document.id),
            metadata={"result": "FAILURE", "reason": failure_str},
        )
        _outbox.append(
            aggregate_type="Document",
            aggregate_id=str(document.id),
            event_type="DOCUMENT.GENERATION.FAILED",
            payload={
                "documentId": str(document.id),
                "quoteId": str(quote.id),
                "failureCode": failure_str,
            },
        )
        raise

    _audit.record(
        action="document.generated",
        entity_type="Document",
        entity_id=str(document.id),
        metadata={"quoteId": str(quote.id), "documentNumber": document_number},
    )
    _outbox.append(
        aggregate_type="Document",
        aggregate_id=str(document.id),
        event_type="DOCUMENT.GENERATED",
        payload={
            "documentId": str(document.id),
            "quoteId": str(quote.id),
            "documentNumber": document_number,
            "templateCode": template.template_code,
            "generatedAt": document.generated_at.isoformat() if document.generated_at else None,
        },
    )
    return document


def get_quote_proposal(*, quote: Quote) -> Document | None:
    return quote.documents.order_by("-requested_at").first()
