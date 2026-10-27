"""Corporate population groups, subgroups and category-based eligibility."""
from __future__ import annotations

import datetime

from django.db import transaction

from apps.client.domain.errors import (
    PopulationGroupConflictError,
    PopulationGroupValidationError,
    RowVersionMismatchError,
)
from apps.client.infrastructure.models import InsuredMember, PopulationGroup, PopulationGroupMember, Proposer
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def _validate_rules(rules: dict) -> dict:
    rules = rules or {}
    allowed = {"relationshipCodes", "minAge", "maxAge", "requireActiveMember"}
    unknown = set(rules) - allowed
    if unknown:
        raise ValueError("Regras de grupo desconhecidas: " + ", ".join(sorted(unknown)))
    if rules.get("minAge") is not None and rules.get("maxAge") is not None and rules["minAge"] > rules["maxAge"]:
        raise ValueError("minAge não pode ser maior que maxAge")
    return rules


def create_group(*, proposer: Proposer, code: str, name: str, category_code: str | None,
                 parent_group_id, eligibility_rules: dict) -> PopulationGroup:
    if proposer.proposer_type != "ORGANISATION":
        raise ValueError("Grupos de população só podem ser criados para empresas")
    tenant = CurrentTenantProvider.require()
    parent = None
    if parent_group_id:
        parent = PopulationGroup.objects.filter(id=parent_group_id, proposer=proposer).first()
        if parent is None:
            raise ValueError("O subgrupo tem de pertencer à mesma empresa")
    with transaction.atomic():
        group = PopulationGroup.objects.create(tenant_id=tenant.value, proposer=proposer, parent_group=parent,
            code=code.strip().upper(), name=name.strip(), category_code=category_code or None,
            eligibility_rules_json=_validate_rules(eligibility_rules))
        _audit.record(action="population_group.created", entity_type="PopulationGroup", entity_id=str(group.id))
        _outbox.append(aggregate_type="PopulationGroup", aggregate_id=str(group.id), event_type="POPULATION_GROUP.CREATED",
                       payload={"groupId": str(group.id), "proposerId": str(proposer.id), "code": group.code})
    return group


def update_group(*, group: PopulationGroup, name: str, category_code: str | None,
                 eligibility_rules: dict, status: str, row_version: int) -> PopulationGroup:
    """Change business rules or activate/deactivate a group with optimistic locking."""
    if status not in {"ACTIVE", "INACTIVE"}:
        raise PopulationGroupValidationError("O estado do grupo tem de ser ACTIVE ou INACTIVE")
    rules = _validate_rules(eligibility_rules)
    updated = PopulationGroup.objects.filter(id=group.id, row_version=row_version).update(
        name=name.strip(), category_code=category_code or None, eligibility_rules_json=rules,
        status=status, row_version=row_version + 1,
    )
    if not updated:
        raise RowVersionMismatchError("O grupo foi alterado entretanto; recarregue e tente novamente")
    group.refresh_from_db()
    _audit.record(action="population_group.updated", entity_type="PopulationGroup", entity_id=str(group.id),
                  metadata={"status": group.status})
    _outbox.append(aggregate_type="PopulationGroup", aggregate_id=str(group.id), event_type="POPULATION_GROUP.UPDATED",
                   payload={"groupId": str(group.id), "status": group.status, "rowVersion": group.row_version})
    return group


def _age_on(date_of_birth, on_date):
    return on_date.year - date_of_birth.year - ((on_date.month, on_date.day) < (date_of_birth.month, date_of_birth.day))


def validate_member_for_group(*, group: PopulationGroup, member: InsuredMember, on_date: datetime.date) -> None:
    if member.proposer_id != group.proposer_id:
        raise ValueError("A pessoa segura tem de pertencer à mesma empresa do grupo")
    if group.status != "ACTIVE":
        raise ValueError("Não é possível incluir pessoas num grupo inativo")
    rules = group.eligibility_rules_json or {}
    if rules.get("requireActiveMember", True) and member.status != "ACTIVE":
        raise ValueError("A pessoa segura tem de estar ativa")
    allowed = rules.get("relationshipCodes") or []
    if allowed and member.relationship_code not in allowed:
        raise ValueError("A relação familiar não é elegível para esta categoria")
    if member.date_of_birth:
        age = _age_on(member.date_of_birth, on_date)
        if rules.get("minAge") is not None and age < int(rules["minAge"]):
            raise ValueError("A pessoa segura não tem a idade mínima da categoria")
        if rules.get("maxAge") is not None and age > int(rules["maxAge"]):
            raise ValueError("A pessoa segura excede a idade máxima da categoria")


def assign_member(*, group: PopulationGroup, member: InsuredMember, category_code: str | None, joined_at: datetime.date) -> PopulationGroupMember:
    validate_member_for_group(group=group, member=member, on_date=joined_at)
    tenant = CurrentTenantProvider.require()
    with transaction.atomic():
        assignment, created = PopulationGroupMember.objects.get_or_create(
            group=group, member=member,
            defaults={"tenant_id": tenant.value, "category_code": category_code or group.category_code, "joined_at": joined_at},
        )
        if not created and assignment.left_at is not None:
            PopulationGroupMember.objects.filter(id=assignment.id).update(left_at=None, joined_at=joined_at,
                category_code=category_code or group.category_code, row_version=assignment.row_version + 1)
            assignment.refresh_from_db()
        elif not created:
            raise ValueError("A pessoa já pertence a este grupo")
        _audit.record(action="population_group.member_assigned", entity_type="PopulationGroup", entity_id=str(group.id),
                      metadata={"memberId": str(member.id)})
    return assignment


def remove_member(*, assignment: PopulationGroupMember, left_at: datetime.date, row_version: int) -> PopulationGroupMember:
    if assignment.left_at is not None:
        raise ValueError("A pessoa já saiu deste grupo")
    if left_at < assignment.joined_at:
        raise ValueError("A data de saída não pode ser anterior à entrada")
    updated = PopulationGroupMember.objects.filter(id=assignment.id, row_version=row_version, left_at__isnull=True).update(
        left_at=left_at, row_version=row_version + 1)
    if not updated:
        raise RowVersionMismatchError("O grupo foi alterado entretanto; recarregue e tente novamente")
    assignment.refresh_from_db()
    _audit.record(action="population_group.member_removed", entity_type="PopulationGroup", entity_id=str(assignment.group_id),
                  metadata={"memberId": str(assignment.member_id), "leftAt": left_at.isoformat()})
    return assignment
