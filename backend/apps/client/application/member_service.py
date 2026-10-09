"""InsuredMember orchestration (Q360-S3-02).

DOC-003 Q360-S3-02 acceptance criteria: "Relação válida • Dependente
requer titular • Datas coerentes". "Datas coerentes" (dateOfBirth not in
the future) is enforced here. "Relação válida" — UPDATED 2026-09-21
(OPEN_DECISIONS.md#S03-RELATIONSHIP-001, OD-003): now means
`relationshipCode` must be one of the tenant's real catalogue values (see
apps/client/application/relationship_service.py), not just a non-empty
string. "Dependente requer titular" is still NOT implemented — that is a
question for the eligibility rules engine (OD-005), which can key off
`RelationshipCode.category` (e.g. CHILD/ASCENDANT require a TITULAR to
exist on the same Proposer), not this module.
"""
from __future__ import annotations

import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.client.application.relationship_service import validate_relationship_code
from apps.client.domain.errors import (
    DuplicateExternalReferenceError,
    IncoherentDateError,
    RowVersionMismatchError,
)
from apps.client.domain.enums import MemberStatus
from apps.client.infrastructure.models import InsuredMember, Proposer

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def _check_date_of_birth_coherent(date_of_birth: datetime.date | None) -> None:
    if date_of_birth is not None and date_of_birth > timezone.now().date():
        raise IncoherentDateError(f"A data de nascimento {date_of_birth} está no futuro")


def create_member(
    *,
    proposer: Proposer,
    relationship_code: str,
    first_name: str | None,
    last_name: str | None,
    date_of_birth: datetime.date | None,
    sex_code: str | None,
    external_reference: str | None,
    attributes: dict[str, Any] | None,
) -> InsuredMember:
    _check_date_of_birth_coherent(date_of_birth)
    tenant_id = CurrentTenantProvider.require()
    validate_relationship_code(tenant_id=tenant_id.value, code=relationship_code)
    try:
        with transaction.atomic():
            member = InsuredMember.objects.create(
                tenant_id=tenant_id.value,
                proposer=proposer,
                relationship_code=relationship_code,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                sex_code=sex_code,
                external_reference=external_reference,
                attributes_json=attributes or {},
            )
    except IntegrityError as exc:
        raise DuplicateExternalReferenceError(
            f"A referência externa '{external_reference}' já existe para o cliente {proposer.id}"
        ) from exc

    _audit.record(action="member.created", entity_type="InsuredMember", entity_id=str(member.id))
    _outbox.append(
        aggregate_type="InsuredMember",
        aggregate_id=str(member.id),
        event_type="MEMBER.CREATED",
        payload={
            "memberId": str(member.id),
            "proposerId": str(proposer.id),
            "relationshipCode": member.relationship_code,
            "firstName": member.first_name,
            "lastName": member.last_name,
            "externalReference": member.external_reference,
        },
    )
    return member


def update_member(
    *,
    member: InsuredMember,
    relationship_code: str,
    first_name: str | None,
    last_name: str | None,
    date_of_birth: datetime.date | None,
    sex_code: str | None,
    attributes: dict[str, Any] | None,
    row_version: int,
) -> InsuredMember:
    _check_date_of_birth_coherent(date_of_birth)
    validate_relationship_code(tenant_id=member.tenant_id, code=relationship_code)
    updated = InsuredMember.objects.filter(id=member.id, row_version=row_version).update(
        relationship_code=relationship_code,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        sex_code=sex_code,
        attributes_json=attributes or {},
        row_version=row_version + 1,
    )
    if updated == 0:
        raise RowVersionMismatchError(
            f"A versão da pessoa segura {member.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
        )
    member.refresh_from_db()
    _audit.record(
        action="member.updated",
        entity_type="InsuredMember",
        entity_id=str(member.id),
        metadata={"rowVersion": member.row_version},
    )
    _outbox.append(
        aggregate_type="InsuredMember",
        aggregate_id=str(member.id),
        event_type="MEMBER.UPDATED",
        payload={
            "memberId": str(member.id),
            "relationshipCode": member.relationship_code,
            "firstName": member.first_name,
            "lastName": member.last_name,
            "rowVersion": member.row_version,
        },
    )
    return member


def deactivate_member(*, member: InsuredMember, row_version: int) -> InsuredMember:
    """The DELETE endpoint performs a safe soft delete.

    Members can be referenced by quotes, eligibility evaluations and pricing
    evidence, so physically deleting one would corrupt historical records.
    """
    updated = InsuredMember.objects.filter(
        id=member.id,
        row_version=row_version,
    ).update(status=MemberStatus.INACTIVE.value, row_version=row_version + 1)
    if updated == 0:
        raise RowVersionMismatchError(
            f"A versão da pessoa segura {member.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
        )
    member.refresh_from_db()
    _audit.record(
        action="member.deactivated",
        entity_type="InsuredMember",
        entity_id=str(member.id),
        metadata={"rowVersion": member.row_version},
    )
    _outbox.append(
        aggregate_type="InsuredMember",
        aggregate_id=str(member.id),
        event_type="MEMBER.DEACTIVATED",
        payload={"memberId": str(member.id), "rowVersion": member.row_version},
    )
    return member
