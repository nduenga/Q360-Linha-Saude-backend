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
            f"RuleVersion {rule_version.id} is not DRAFT; only a DRAFT rule version can be edited"
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
            f"RuleVersion {rule_version.id} is not DRAFT; only a DRAFT rule version can be deleted"
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
            f"RuleVersion {rule_version.id} is not PUBLISHED; only a PUBLISHED rule version can be retired"
        )
    rule_version.refresh_from_db()
    _audit.record(
        action="rule_version.retired", entity_type="RuleVersion", entity_id=str(rule_version.id),
        metadata={"versionNo": rule_version.version_no},
    )
    return rule_version


def publish_rule_version(rule_version: RuleVersion) -> RuleVersion:
    actor = CurrentActorProvider.get()
    updated = RuleVersion.objects.filter(id=rule_version.id, status="DRAFT").update(
        status="PUBLISHED",
        published_at=timezone.now(),
        published_by=actor.actor_id if actor else None,
    )
    if updated == 0:
        raise RuleVersionImmutableError(
            f"RuleVersion {rule_version.id} is not DRAFT; only DRAFT can be published"
        )
    rule_version.refresh_from_db()

    _audit.record(
        action="rule_version.published",
        entity_type="RuleVersion",
        entity_id=str(rule_version.id),
        metadata={"versionNo": rule_version.version_no},
    )
    return rule_version
