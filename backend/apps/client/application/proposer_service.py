"""Proposer orchestration (Q360-S3-01)."""
from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.client.domain.errors import DuplicateExternalReferenceError, RowVersionMismatchError
from apps.client.infrastructure.models import Proposer

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def create_proposer(
    *,
    proposer_type: str,
    display_name: str,
    external_reference: str | None,
    registration_number: str,
    email: str,
    phone: str,
    attributes: dict[str, Any] | None,
) -> Proposer:
    tenant_id = CurrentTenantProvider.require()
    try:
        with transaction.atomic():
            proposer = Proposer.objects.create(
                tenant_id=tenant_id.value,
                proposer_type=proposer_type,
                display_name=display_name,
                external_reference=external_reference,
                registration_number=registration_number,
                email=email,
                phone=phone,
                attributes_json=attributes or {},
            )
    except IntegrityError as exc:
        raise DuplicateExternalReferenceError(
            f"externalReference '{external_reference}' already exists for this tenant"
        ) from exc

    _audit.record(action="proposer.created", entity_type="Proposer", entity_id=str(proposer.id))
    _outbox.append(
        aggregate_type="Proposer",
        aggregate_id=str(proposer.id),
        event_type="PROPOSER.CREATED",
        payload={
            "proposerId": str(proposer.id),
            "proposerType": proposer.proposer_type,
            "displayName": proposer.display_name,
            "externalReference": proposer.external_reference,
        },
    )
    return proposer


def update_proposer(
    *,
    proposer: Proposer,
    display_name: str,
    registration_number: str,
    email: str,
    phone: str,
    attributes: dict[str, Any] | None,
    row_version: int,
) -> Proposer:
    updated = Proposer.objects.filter(id=proposer.id, row_version=row_version).update(
        display_name=display_name,
        registration_number=registration_number,
        email=email,
        phone=phone,
        attributes_json=attributes or {},
        row_version=row_version + 1,
    )
    if updated == 0:
        raise RowVersionMismatchError(
            f"Proposer {proposer.id} rowVersion {row_version} does not match the current version"
        )
    proposer.refresh_from_db()
    _audit.record(
        action="proposer.updated",
        entity_type="Proposer",
        entity_id=str(proposer.id),
        metadata={"rowVersion": proposer.row_version},
    )
    _outbox.append(
        aggregate_type="Proposer",
        aggregate_id=str(proposer.id),
        event_type="PROPOSER.UPDATED",
        payload={
            "proposerId": str(proposer.id),
            "displayName": proposer.display_name,
            "rowVersion": proposer.row_version,
        },
    )
    return proposer
