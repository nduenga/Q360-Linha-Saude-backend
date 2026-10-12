"""Proposer orchestration (Q360-S3-01)."""
from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
import datetime

from apps.client.domain.enums import ProposerType
from apps.client.domain.errors import (
    DuplicateExternalReferenceError,
    DuplicateNifError,
    InvalidNifError,
    RowVersionMismatchError,
)
from apps.client.domain.nif import NifFormatError, validate_agt_nif
from apps.client.domain.rules import require_date_of_birth
from apps.client.infrastructure.models import Proposer

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def _canonical_nif(nif: str, proposer_type: str) -> str:
    """NIF por tipo: INDIVIDUAL = 14 caracteres; ORGANISATION = 10 dígitos.
    Última barreira — vale para a API, para `createQuote` inline, etc."""
    try:
        return validate_agt_nif(nif, proposer_type)
    except NifFormatError as exc:
        raise InvalidNifError(str(exc)) from exc


def _check_date_of_birth(proposer_type: str, date_of_birth: datetime.date | None, *, required: bool):
    """Proponente individual: data de nascimento obrigatória (quando
    `required`). Empresa: não tem data de nascimento."""
    if proposer_type != ProposerType.INDIVIDUAL.value:
        return None
    if date_of_birth is None and not required:
        return None
    return require_date_of_birth(date_of_birth, who="proponente individual")


def create_proposer(
    *,
    proposer_type: str,
    display_name: str,
    external_reference: str | None,
    nif: str,
    registration_number: str,
    email: str,
    phone: str,
    address: str | None = None,
    attributes: dict[str, Any] | None,
    date_of_birth: datetime.date | None = None,
    require_birth_date: bool = False,
) -> Proposer:
    """`require_birth_date=True` é passado pela API/`createQuote` (obrigatório
    para INDIVIDUAL); scripts de seed antigos continuam a funcionar sem ele."""
    tenant_id = CurrentTenantProvider.require()
    nif = _canonical_nif(nif, proposer_type)
    registration_number = nif
    date_of_birth = _check_date_of_birth(proposer_type, date_of_birth, required=require_birth_date)
    try:
        with transaction.atomic():
            if Proposer.objects.filter(nif=nif).exists():
                raise DuplicateNifError(f"Já existe um proponente com o NIF '{nif}' neste tenant.")
            proposer = Proposer.objects.create(
                tenant_id=tenant_id.value,
                proposer_type=proposer_type,
                display_name=display_name,
                external_reference=external_reference,
                nif=nif,
                registration_number=registration_number,
                email=email,
                phone=phone,
                address=address,
                date_of_birth=date_of_birth,
                attributes_json=attributes or {},
            )
    except IntegrityError as exc:
        if Proposer.objects.filter(nif=nif).exists():
            raise DuplicateNifError(f"Já existe um proponente com o NIF '{nif}' neste tenant.") from exc
        raise DuplicateExternalReferenceError(
            f"A referência externa '{external_reference}' já existe neste tenant"
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
    nif: str,
    registration_number: str,
    email: str,
    phone: str,
    address: str | None = None,
    attributes: dict[str, Any] | None,
    row_version: int,
    date_of_birth: datetime.date | None = None,
    require_birth_date: bool = False,
) -> Proposer:
    # O tipo de proponente não muda numa edição: é ele que decide o formato do NIF.
    nif = _canonical_nif(nif, proposer.proposer_type)
    registration_number = nif
    date_of_birth = _check_date_of_birth(proposer.proposer_type, date_of_birth, required=require_birth_date)
    if date_of_birth is None:
        date_of_birth = proposer.date_of_birth  # não apagar uma data já guardada
    try:
        updated = Proposer.objects.filter(id=proposer.id, row_version=row_version).update(
            display_name=display_name,
            registration_number=registration_number,
            nif=nif,
            email=email,
            phone=phone,
            address=address,
            date_of_birth=date_of_birth,
            attributes_json=attributes or {},
            row_version=row_version + 1,
        )
    except IntegrityError as exc:
        raise DuplicateNifError(f"Já existe um proponente com o NIF '{nif}' neste tenant.") from exc
    if updated == 0:
        raise RowVersionMismatchError(
            f"A versão do cliente {proposer.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
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


def deactivate_proposer(
    *,
    proposer: Proposer,
    row_version: int,
) -> Proposer:
    updated = (
        Proposer.objects
        .filter(
            id=proposer.id,
            row_version=row_version,
        )
        .update(
            status="INACTIVE",
            row_version=row_version + 1,
        )
    )

    if updated == 0:
        raise RowVersionMismatchError(
            f"A versão do cliente {proposer.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
        )

    proposer.refresh_from_db()

    _audit.record(
        action="proposer.deactivated",
        entity_type="Proposer",
        entity_id=str(proposer.id),
        metadata={
            "rowVersion": proposer.row_version,
        },
    )

    _outbox.append(
        aggregate_type="Proposer",
        aggregate_id=str(proposer.id),
        event_type="PROPOSER.DEACTIVATED",
        payload={
            "proposerId": str(proposer.id),
            "rowVersion": proposer.row_version,
        },
    )

    return proposer
