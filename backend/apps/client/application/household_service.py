"""Optional family households for an organisation's insured population."""
from __future__ import annotations

import datetime

from django.db import transaction

from apps.client.application.relationship_service import validate_relationship_code
from apps.client.domain.enums import MemberStatus, ProposerType, RelationshipCategory
from apps.client.domain.errors import HouseholdConflictError, HouseholdValidationError, RowVersionMismatchError
from apps.client.infrastructure.models import FamilyHousehold, FamilyHouseholdMember, InsuredMember, Proposer
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
        )
        FamilyHouseholdMember.objects.create(
            tenant_id=tenant.value, household=household, member=primary_member, joined_at=joined_at,
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
        if FamilyHouseholdMember.objects.filter(member=member).exists():
            raise HouseholdConflictError("A pessoa segura já pertence a um agregado familiar.")
        membership = FamilyHouseholdMember.objects.create(
            tenant_id=household.tenant_id, household=household, member=member, joined_at=joined_at,
        )
    _audit.record(action="household.dependent_added", entity_type="FamilyHousehold", entity_id=str(household.id),
                  metadata={"memberId": str(member.id)})
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
