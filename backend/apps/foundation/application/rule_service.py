"""RuleSet/RuleVersion orchestration (ART-006 `createRuleVersion`,
`publishConfiguration` for configType=rule-version).

Built now (not deferred to Sprint 5) because Q360-S3-03's own acceptance
criteria requires demonstrating ELIGIBLE/WARNING/REFERRAL/HARD_STOP
decisions, all but HARD_STOP requiring a real, published, rule_domain=
ELIGIBILITY RuleVersion to exist — without this endpoint, eligibility
evaluation could never leave CONFIG_ERROR. See
OPEN_DECISIONS.md#S03-ELIGIBILITY-001.
"""
from __future__ import annotations

import datetime

from django.db import transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.foundation.infrastructure.models import RuleSet, RuleVersion

_audit = AuditService(DjangoAuditRepositoryAdapter())


class RuleVersionImmutableError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


class RuleVersionLimitError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _check_eligibility_limits(rule_version: RuleVersion) -> None:
    """Uma regra de elegibilidade não pode passar a maioridade (sem prova) nem
    o teto de idade com prova definidos pelo fornecedor — nem nas regras
    gerais nem nas exceções corporativas."""
    import json

    from apps.foundation.application import system_parameter_service

    if rule_version.rule_set.rule_domain != "ELIGIBILITY" or rule_version.artifact_type != "JSON":
        return
    try:
        raw = json.loads(rule_version.artifact_ref or "{}")
    except (TypeError, ValueError):
        return
    if not isinstance(raw, dict):
        return
    majority = system_parameter_service.get_value("legal.age_of_majority")
    with_proof = system_parameter_service.get_value("limits.dependent_max_age_with_proof")
    blocks = [("regras gerais", raw.get("categoryRules") or {})]
    for org, override in (raw.get("corporateOverrides") or {}).items():
        if isinstance(override, dict):
            blocks.append((f"exceção corporativa {org}", override.get("categoryRules") or {}))
    for where, rules in blocks:
        child = rules.get("CHILD") if isinstance(rules, dict) else None
        if not isinstance(child, dict):
            continue
        without = child.get("maxAgeWithoutProof")
        if isinstance(without, int) and majority is not None and without > majority:
            raise RuleVersionLimitError(
                f"Filhos ({where}): sem prova só até à maioridade ({majority} anos, legal.age_of_majority); "
                f"indicado {without}"
            )
        proof = child.get("maxAgeWithProof")
        if isinstance(proof, int) and with_proof is not None and proof > with_proof:
            raise RuleVersionLimitError(
                f"Filhos ({where}): com prova de estudos até {with_proof} anos no máximo "
                f"(limits.dependent_max_age_with_proof); indicado {proof}"
            )


def create_rule_version(
    *,
    code: str,
    name: str,
    rule_domain: str,
    effective_from: datetime.date,
    effective_to: datetime.date | None,
    artifact_type: str,
    artifact_ref: str | None,
    artifact_checksum: str | None,
) -> RuleVersion:
    tenant_id = CurrentTenantProvider.require()
    with transaction.atomic():
        rule_set, _ = RuleSet.objects.get_or_create(
            code=code, defaults={"tenant_id": tenant_id.value, "name": name, "rule_domain": rule_domain}
        )
        next_version_no = (
            RuleVersion.objects.filter(rule_set=rule_set)
            .order_by("-version_no")
            .values_list("version_no", flat=True)
            .first()
            or 0
        ) + 1
        rule_version = RuleVersion.objects.create(
            tenant_id=tenant_id.value,
            rule_set=rule_set,
            version_no=next_version_no,
            effective_from=effective_from,
            effective_to=effective_to,
            artifact_type=artifact_type,
            artifact_ref=artifact_ref,
            artifact_checksum=artifact_checksum,
        )

    _audit.record(
        action="rule_version.created",
        entity_type="RuleVersion",
        entity_id=str(rule_version.id),
        metadata={"code": code, "ruleDomain": rule_domain, "versionNo": rule_version.version_no},
    )
    return rule_version


def update_rule_version(
    rule_version: RuleVersion,
    *,
    name: str,
    artifact_type: str,
    artifact_ref: str | None,
    artifact_checksum: str | None,
) -> RuleVersion:
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6: only a DRAFT RuleVersion
    can be edited — once PUBLISHED, correcting it means creating the next
    version via create_rule_version, never mutating a version eligibility/
    pricing evaluations may already reference."""
    updated = RuleVersion.objects.filter(id=rule_version.id, status="DRAFT").update(
        artifact_type=artifact_type, artifact_ref=artifact_ref, artifact_checksum=artifact_checksum
    )
    if updated == 0:
        raise RuleVersionImmutableError(
            f"A versão de regra {rule_version.id} não está em rascunho (DRAFT); só um rascunho pode ser editado"
        )
    RuleSet.objects.filter(id=rule_version.rule_set_id).update(name=name)
    rule_version.refresh_from_db()

    _audit.record(
        action="rule_version.updated",
        entity_type="RuleVersion",
        entity_id=str(rule_version.id),
        metadata={"versionNo": rule_version.version_no},
    )
    return rule_version


def delete_rule_version(rule_version: RuleVersion) -> None:
    """Only a DRAFT rule version can be deleted."""
    deleted, _ = RuleVersion.objects.filter(id=rule_version.id, status="DRAFT").delete()
    if deleted == 0:
        raise RuleVersionImmutableError(
            f"A versão de regra {rule_version.id} não está em rascunho (DRAFT); só um rascunho pode ser eliminado"
        )
    _audit.record(
        action="rule_version.deleted", entity_type="RuleVersion", entity_id=str(rule_version.id),
        metadata={"versionNo": rule_version.version_no},
    )


def retire_rule_version(rule_version: RuleVersion) -> RuleVersion:
    """OD-ANGOLA-006: "remover" on something PUBLISHED means retire, not
    delete."""
    updated = RuleVersion.objects.filter(id=rule_version.id, status="PUBLISHED").update(status="RETIRED")
    if updated == 0:
        raise RuleVersionImmutableError(
            f"A versão de regra {rule_version.id} não está publicada (PUBLISHED); só uma versão publicada pode ser retirada"
        )
    rule_version.refresh_from_db()
    _audit.record(
        action="rule_version.retired", entity_type="RuleVersion", entity_id=str(rule_version.id),
        metadata={"versionNo": rule_version.version_no},
    )
    return rule_version


def publish_rule_version(rule_version: RuleVersion) -> RuleVersion:
    _check_eligibility_limits(rule_version)
    actor = CurrentActorProvider.get()
    updated = RuleVersion.objects.filter(id=rule_version.id, status="DRAFT").update(
        status="PUBLISHED",
        published_at=timezone.now(),
        published_by=actor.actor_id if actor else None,
    )
    if updated == 0:
        raise RuleVersionImmutableError(
            f"A versão de regra {rule_version.id} não está em rascunho (DRAFT); só um rascunho pode ser publicado"
        )
    rule_version.refresh_from_db()

    _audit.record(
        action="rule_version.published",
        entity_type="RuleVersion",
        entity_id=str(rule_version.id),
        metadata={"versionNo": rule_version.version_no},
    )
    return rule_version
