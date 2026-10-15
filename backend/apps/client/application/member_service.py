"""InsuredMember orchestration (Q360-S3-02).

DOC-003 Q360-S3-02 acceptance criteria: "Relação válida • Dependente
requer titular • Datas coerentes". "Datas coerentes" (dateOfBirth not in
the future) is enforced here. "Relação válida" — UPDATED 2026-09-21
(OPEN_DECISIONS.md#S03-RELATIONSHIP-001, OD-003): now means
`relationshipCode` must be one of the tenant's real catalogue values (see
apps/client/application/relationship_service.py), not just a non-empty
string.

UPDATED 2026-10 (Product Owner): este módulo passa a impor também
  - data de nascimento obrigatória para toda a pessoa segura;
  - existência de um TITULAR antes de qualquer outra relação;
  - diferença mínima de 13 anos entre titular e filho(a) / ascendente;
  - limite configurável de beneficiários (proponente individual);
  - um único titular num proponente individual.
As regras puras vivem em `apps.client.domain.rules.validate_household`.
O email/telefone NUNCA são pedidos à pessoa segura: herdam os do proponente
(titular), que os guarda em `Proposer.email` / `Proposer.phone`.
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
    DuplicateMemberNifError,
    RowVersionMismatchError,
)
from apps.client.domain.enums import MemberStatus, ProposerType, RelationshipCategory
from apps.client.domain.rules import Person, require_date_of_birth, validate_household
from apps.client.infrastructure.models import InsuredMember, Proposer, RelationshipCode

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


MAX_BENEFICIARIES_PARAMETER = "client.individual_max_beneficiaries"


def max_beneficiaries_for_individual() -> int | None:
    """Limite configurável pelo GTE (Parâmetros do sistema). `None` = sem limite."""
    from apps.foundation.application import system_parameter_service

    return system_parameter_service.get_value(MAX_BENEFICIARIES_PARAMETER)


def _category_by_code() -> dict[str, str]:
    return {rc.code: rc.category for rc in RelationshipCode.objects.all()}


def _person_label(first_name: str | None, last_name: str | None) -> str:
    return " ".join(x for x in (first_name, last_name) if x)


def _validate_population(
    *,
    proposer: Proposer,
    candidate: Person | None,
    exclude_member_id=None,
    titular_rule_only: bool = False,
) -> None:
    """Aplica as regras ao conjunto FINAL de pessoas ativas do proponente:
    as atuais (sem `exclude_member_id`) mais o `candidate` (quando existe).
    Serve para criar, editar e desativar."""
    categories = _category_by_code()
    people: list[Person] = []
    for other in InsuredMember.objects.filter(proposer=proposer, status=MemberStatus.ACTIVE.value):
        if exclude_member_id is not None and other.id == exclude_member_id:
            continue
        people.append(
            Person(
                category=categories.get(other.relationship_code, RelationshipCategory.OTHER.value),
                date_of_birth=other.date_of_birth,
                label=_person_label(other.first_name, other.last_name),
            )
        )
    if candidate is not None:
        people.append(candidate)
    individual = proposer.proposer_type == ProposerType.INDIVIDUAL.value and not titular_rule_only
    validate_household(
        people,
        individual=individual,
        max_beneficiaries=max_beneficiaries_for_individual() if individual else None,
    )


def _raise_if_nif_taken(
    nif: str | None, *, proposer_id, exclude_member_id=None, exc: Exception | None = None
) -> None:
    """R1: o NIF da pessoa segura é opcional, mas único no tomador; a mesma
    pessoa pode ter ficha com o NIF noutro tomador."""
    if not nif:
        return
    taken = InsuredMember.objects.filter(proposer_id=proposer_id, nif=nif)
    if exclude_member_id is not None:
        taken = taken.exclude(id=exclude_member_id)
    if taken.exists():
        raise DuplicateMemberNifError(f"Já existe uma pessoa segura com o NIF '{nif}' neste cliente.") from exc


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
    nif: str | None = None,
) -> InsuredMember:
    date_of_birth = require_date_of_birth(date_of_birth)
    tenant_id = CurrentTenantProvider.require()
    rel = validate_relationship_code(tenant_id=tenant_id.value, code=relationship_code)
    _raise_if_nif_taken(nif, proposer_id=proposer.id)
    try:
        with transaction.atomic():
            # Bloqueia o proponente para duas criações em paralelo não furarem o limite.
            Proposer.objects.select_for_update().filter(id=proposer.id).first()
            _validate_population(
                proposer=proposer,
                candidate=Person(rel.category, date_of_birth, _person_label(first_name, last_name)),
            )
            member = InsuredMember.objects.create(
                tenant_id=tenant_id.value,
                proposer=proposer,
                relationship_code=relationship_code,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                sex_code=sex_code,
                nif=nif,
                external_reference=external_reference,
                attributes_json=attributes or {},
            )
    except IntegrityError as exc:
        _raise_if_nif_taken(nif, proposer_id=proposer.id, exc=exc)
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
    nif: str | None = None,
    keep_nif: bool = True,
) -> InsuredMember:
    """`keep_nif=True` (omitido no pedido) preserva o NIF guardado."""
    date_of_birth = require_date_of_birth(date_of_birth)
    rel = validate_relationship_code(tenant_id=member.tenant_id, code=relationship_code)
    if not keep_nif:
        _raise_if_nif_taken(nif, proposer_id=member.proposer_id, exclude_member_id=member.id)
    try:
        with transaction.atomic():
            proposer = Proposer.objects.select_for_update().get(id=member.proposer_id)
            if member.status == MemberStatus.ACTIVE.value:
                _validate_population(
                    proposer=proposer,
                    candidate=Person(rel.category, date_of_birth, _person_label(first_name, last_name)),
                    exclude_member_id=member.id,
                )
            updated = InsuredMember.objects.filter(id=member.id, row_version=row_version).update(
                relationship_code=relationship_code,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                sex_code=sex_code,
                nif=member.nif if keep_nif else nif,
                attributes_json=attributes or {},
                row_version=row_version + 1,
            )
    except IntegrityError as exc:  # corrida perdida com outra pessoa segura com o mesmo NIF
        raise DuplicateMemberNifError(f"Já existe uma pessoa segura com o NIF '{nif}' neste cliente.") from exc
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
    # Não se pode desativar o titular enquanto houver outras relações ativas.
    proposer = Proposer.objects.get(id=member.proposer_id)
    _validate_population(proposer=proposer, candidate=None, exclude_member_id=member.id, titular_rule_only=True)
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
