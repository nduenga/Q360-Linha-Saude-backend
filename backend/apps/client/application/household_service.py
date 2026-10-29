"""Optional family households for an organisation's insured population."""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from django.db import transaction

from apps.client.application.relationship_service import validate_relationship_code
from apps.client.application import member_service
from apps.client.domain.enums import MemberStatus, ProposerType, RelationshipCategory
from apps.client.domain.errors import HouseholdConflictError, HouseholdValidationError, RowVersionMismatchError
from apps.client.infrastructure.models import FamilyHousehold, FamilyHouseholdMember, InsuredMember, Person, Proposer
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def _require_corporate_holder(*, proposer: Proposer, member: InsuredMember) -> None:
    if proposer.proposer_type != ProposerType.ORGANISATION.value:
        raise HouseholdValidationError("Os agregados familiares são exclusivos de empresas.")
    if member.proposer_id != proposer.id or member.status != MemberStatus.ACTIVE.value:
        raise HouseholdValidationError("O titular tem de ser uma pessoa segura ativa da mesma empresa.")
    relationship = validate_relationship_code(tenant_id=member.tenant_id, code=member.relationship_code)
    if relationship.category != RelationshipCategory.TITULAR.value:
        raise HouseholdValidationError("O membro indicado tem de ter a relação TITULAR.")


def create_household(*, proposer: Proposer, primary_member: InsuredMember, joined_at: datetime.date) -> FamilyHousehold:
    """Create an optional household. Its holder becomes the first membership."""
    _require_corporate_holder(proposer=proposer, member=primary_member)
    tenant = CurrentTenantProvider.require()
    with transaction.atomic():
        if FamilyHousehold.objects.filter(primary_member=primary_member).exists():
            raise HouseholdConflictError("Este titular já possui um agregado familiar.")
        if FamilyHouseholdMember.objects.filter(member=primary_member).exists():
            raise HouseholdConflictError("Este titular já pertence a um agregado familiar.")
        household = FamilyHousehold.objects.create(
            tenant_id=tenant.value, proposer=proposer, primary_member=primary_member,
            primary_person=primary_member.person,
        )
        FamilyHouseholdMember.objects.create(
            tenant_id=tenant.value, household=household, member=primary_member,
            person=primary_member.person, relationship_code=primary_member.relationship_code, joined_at=joined_at,
        )
    _audit.record(action="household.created", entity_type="FamilyHousehold", entity_id=str(household.id),
                  metadata={"primaryMemberId": str(primary_member.id)})
    _outbox.append(aggregate_type="FamilyHousehold", aggregate_id=str(household.id), event_type="HOUSEHOLD.CREATED",
                   payload={"householdId": str(household.id), "proposerId": str(proposer.id), "primaryMemberId": str(primary_member.id)})
    return household


def add_dependent(*, household: FamilyHousehold, member: InsuredMember, joined_at: datetime.date) -> FamilyHouseholdMember:
    if household.status != "ACTIVE":
        raise HouseholdValidationError("Não é possível incluir dependentes num agregado inativo.")
    if member.proposer_id != household.proposer_id or member.status != MemberStatus.ACTIVE.value:
        raise HouseholdValidationError("O dependente tem de ser uma pessoa segura ativa da mesma empresa.")
    relationship = validate_relationship_code(tenant_id=member.tenant_id, code=member.relationship_code)
    if relationship.category == RelationshipCategory.TITULAR.value:
        raise HouseholdValidationError("Um titular deve criar o seu próprio agregado; não pode ser dependente.")
    with transaction.atomic():
        existing_by_person = FamilyHouseholdMember.objects.filter(
            household=household, person_id=member.person_id, left_at__isnull=True,
        ).first() if member.person_id else None
        if existing_by_person:
            FamilyHouseholdMember.objects.filter(id=existing_by_person.id).update(
                member=member, relationship_code=member.relationship_code,
            )
            existing_by_person.refresh_from_db()
            membership = existing_by_person
        elif FamilyHouseholdMember.objects.filter(member=member).exists():
            raise HouseholdConflictError("A pessoa segura já pertence a um agregado familiar.")
        else:
            membership = FamilyHouseholdMember.objects.create(
                tenant_id=household.tenant_id, household=household, member=member,
                person=member.person, relationship_code=member.relationship_code, joined_at=joined_at,
            )
    _audit.record(action="household.dependent_added", entity_type="FamilyHousehold", entity_id=str(household.id),
                  metadata={"memberId": str(member.id)})
    return membership


def create_dependent(
    *,
    household: FamilyHousehold,
    relationship_code: str,
    first_name: str,
    last_name: str | None,
    date_of_birth: datetime.date,
    sex_code: str | None,
    external_reference: str | None,
    attributes: dict[str, Any] | None,
    nif: str | None,
    joined_at: datetime.date,
) -> FamilyHouseholdMember:
    """Create a dependent in the company's insured population and link it.

    A household never owns an anonymous person: quotes, underwriting and a
    future policy need a stable insured-member identity.  This convenience
    command removes the UI's former two-step requirement while retaining that
    invariant.  All writes are atomic, so an invalid relationship or failed
    household link does not leave a newly-created member behind.
    """
    if household.status != "ACTIVE":
        raise HouseholdValidationError("Não é possível incluir dependentes num agregado inativo.")
    if household.proposer.proposer_type != ProposerType.ORGANISATION.value:
        raise HouseholdValidationError("Os agregados familiares são exclusivos de empresas.")

    tenant = CurrentTenantProvider.require()
    relationship = validate_relationship_code(tenant_id=tenant.value, code=relationship_code)
    if relationship.category == RelationshipCategory.TITULAR.value:
        raise HouseholdValidationError("Use a relação de dependente; TITULAR não pode ser criado como familiar.")

    with transaction.atomic():
        member = member_service.create_member(
            proposer=household.proposer,
            relationship_code=relationship_code,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            sex_code=sex_code,
            external_reference=external_reference,
            attributes=attributes,
            nif=nif,
        )
        membership = add_dependent(household=household, member=member, joined_at=joined_at)
    return membership


def create_household_person(
    *, household: FamilyHousehold, relationship_code: str, joined_at: datetime.date,
    person_id: uuid.UUID | None = None, first_name: str | None = None,
    last_name: str | None = None, date_of_birth: datetime.date | None = None,
    sex_code: str | None = None, nif: str | None = None,
) -> FamilyHouseholdMember:
    """Create a civil person and household link without enrolling them for insurance."""
    if household.status != "ACTIVE":
        raise HouseholdValidationError("Não é possível incluir familiares num agregado inativo.")
    if household.proposer.proposer_type != ProposerType.ORGANISATION.value:
        raise HouseholdValidationError("Os agregados familiares são exclusivos de empresas.")
    tenant = CurrentTenantProvider.require()
    relationship = validate_relationship_code(tenant_id=tenant.value, code=relationship_code)
    if relationship.category == RelationshipCategory.TITULAR.value:
        raise HouseholdValidationError("Use uma relação de dependente; TITULAR não pode ser criado como familiar.")

    with transaction.atomic():
        if person_id:
            person = Person.objects.select_for_update().filter(id=person_id, tenant_id=tenant.value).first()
            if person is None:
                raise HouseholdValidationError("A pessoa indicada não existe neste espaço de trabalho.")
        else:
            person = Person.objects.create(
                tenant_id=tenant.value, first_name=first_name or "Pessoa", last_name=last_name,
                date_of_birth=date_of_birth, sex_code=sex_code, nif=nif,
            )
        if FamilyHouseholdMember.objects.filter(
            person=person, household__proposer_id=household.proposer_id, left_at__isnull=True,
        ).exists():
            raise HouseholdConflictError("Esta pessoa já está associada a outro núcleo deste tomador.")
        membership = FamilyHouseholdMember.objects.create(
            tenant_id=tenant.value, household=household, person=person,
            relationship_code=relationship_code, joined_at=joined_at,
        )
    _audit.record(action="household.person_dependent_created", entity_type="FamilyHousehold",
                  entity_id=str(household.id), metadata={"personId": str(person.id), "relationshipCode": relationship_code})
    _outbox.append(aggregate_type="FamilyHousehold", aggregate_id=str(household.id),
                   event_type="HOUSEHOLD.PERSON_DEPENDENT_ADDED",
                   payload={"householdId": str(household.id), "personId": str(person.id), "relationshipCode": relationship_code})
    return membership


def remove_dependent(*, membership: FamilyHouseholdMember, left_at: datetime.date, row_version: int) -> FamilyHouseholdMember:
    if membership.member_id == membership.household.primary_member_id:
        raise HouseholdValidationError("O titular não pode ser removido do seu agregado familiar.")
    if membership.left_at is not None:
        raise HouseholdConflictError("O dependente já saiu deste agregado familiar.")
    if left_at < membership.joined_at:
        raise HouseholdValidationError("A data de saída não pode ser anterior à entrada.")
    updated = FamilyHouseholdMember.objects.filter(id=membership.id, row_version=row_version, left_at__isnull=True).update(
        left_at=left_at, row_version=row_version + 1,
    )
    if not updated:
        raise RowVersionMismatchError("O agregado foi alterado entretanto; recarregue e tente novamente")
    membership.refresh_from_db()
    _audit.record(action="household.dependent_removed", entity_type="FamilyHousehold", entity_id=str(membership.household_id),
                  metadata={"memberId": str(membership.member_id), "leftAt": left_at.isoformat()})
    return membership
