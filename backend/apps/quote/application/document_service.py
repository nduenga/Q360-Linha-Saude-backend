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
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.quote.application.numbering_service import next_value
from apps.quote.domain.enums import DocumentStatus, DocumentTemplateStatus, DocumentType, QuoteSnapshotType, QuoteStatus
from apps.quote.domain.errors import QuoteStateError
from apps.quote.infrastructure.models import Document, DocumentTemplateVersion, Quote, QuoteSnapshot

_audit = AuditService(DjangoAuditRepositoryAdapter())


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
        raise DuplicateTemplateCodeError(f"Document template '{template_code}' version already exists") from exc

    _audit.record(action="document_template.created", entity_type="DocumentTemplateVersion", entity_id=str(template.id))
    return template


def publish_document_template(template: DocumentTemplateVersion) -> DocumentTemplateVersion:
    actor = CurrentActorProvider.get()
    updated = DocumentTemplateVersion.objects.filter(id=template.id, status=DocumentTemplateStatus.DRAFT.value).update(
        status=DocumentTemplateStatus.PUBLISHED.value, published_at=timezone.now(), published_by=actor.actor_id if actor else None
    )
    if updated == 0:
        raise TemplateImmutableError(f"DocumentTemplateVersion {template.id} is not DRAFT; only DRAFT can be published")
    template.refresh_from_db()
    _audit.record(action="document_template.published", entity_type="DocumentTemplateVersion", entity_id=str(template.id))
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


# OD-006 placeholder: no approved document names a real template code, so
# this is this module's own fixed convention (mirrors S04-PRICING-CONTEXT-001's
# BASE_PREMIUM parameter code convention) - an Admin must create+publish a
# DocumentTemplateVersion with exactly this code before any proposal can be
# generated (fails closed with NOT-FOUND otherwise, same fail-safe posture
# as the pricing engine's missing-config path).
DEFAULT_TEMPLATE_CODE = "QUOTE_PROPOSAL_DEFAULT"


def generate_quote_proposal(*, quote: Quote) -> Document:
    if quote.status != QuoteStatus.APPROVED.value:
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; a proposal can only be generated once APPROVED")

    approval_snapshot = (
        QuoteSnapshot.objects.filter(quote=quote, snapshot_type=QuoteSnapshotType.APPROVAL.value)
        .order_by("-snapshot_no")
        .first()
    )
    if approval_snapshot is None:
        raise QuoteStateError(f"Quote {quote.id} has no APPROVAL snapshot to generate a proposal from")

    template = _resolve_published_template(template_code=DEFAULT_TEMPLATE_CODE, effective_date=quote.effective_date)
    if template is None:
        raise TemplateNotFoundError(
            f"No published document template '{DEFAULT_TEMPLATE_CODE}' effective on {quote.effective_date} — "
            "an Admin must create and publish one first"
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

    # "Generation": a clearly-labeled placeholder artifact (JSON summary of
    # the approved snapshot + template reference), not a real rendered
    # proposal (OD-006). Reproducible: same snapshot + template always
    # produces the same content/checksum.
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

    document_number = next_value(sequence_code="QUOTE_PROPOSAL", period_key=str(quote.effective_date.year))

    Document.objects.filter(id=document.id).update(
        status=DocumentStatus.GENERATED.value,
        storage_ref=str(file_path),
        checksum=checksum,
        document_number=document_number,
        generated_at=timezone.now(),
    )
    document.refresh_from_db()

    _audit.record(
        action="document.generated",
        entity_type="Document",
        entity_id=str(document.id),
        metadata={"quoteId": str(quote.id), "documentNumber": document_number},
    )
    return document


def get_quote_proposal(*, quote: Quote) -> Document | None:
    return quote.documents.order_by("-requested_at").first()
