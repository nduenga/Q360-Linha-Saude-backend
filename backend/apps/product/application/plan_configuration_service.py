"""Configuração de planos pelo GTE (requisitos R4/R7): definições do plano,
configuração de cada cobertura (capitais, participação, carências) e
validação global do plano.

Tudo é parametrização — sem código — e fica em auditoria com `before`/`after`.
As regras de validação vivem em `apps.product.domain.plan_settings` e
`apps.product.domain.coverage_config` (puras, testáveis sem base de dados).
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.domain.coverage_config import plan_completeness_issues, validate_coverage_config
from apps.product.domain.enums import BenefitStatus
from apps.product.domain.errors import InvalidBenefitSelectionError, RowVersionMismatchError
from apps.product.domain.plan_settings import validate_plan_settings
from apps.product.infrastructure.models import Benefit, Plan, PlanBenefit

_audit = AuditService(DjangoAuditRepositoryAdapter())


def set_plan_settings(*, plan: Plan, settings: dict[str, Any], row_version: int) -> tuple[Plan, list[dict[str, str]]]:
    """Replaces `plan.settings_json` (optimistic locking, like every Plan edit)."""
    normalised, warnings = validate_plan_settings(settings)
    before = plan.settings_json
    updated = Plan.objects.filter(id=plan.id, row_version=row_version).update(
        settings_json=normalised, row_version=row_version + 1
    )
    if updated == 0:
        raise RowVersionMismatchError(f"A versão do plano {plan.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo")
    plan.refresh_from_db()
    _audit.record(
        action="plan.settings_updated",
        entity_type="Plan",
        entity_id=str(plan.id),
        metadata=change_metadata(before=before, after=plan.settings_json),
    )
    return plan, warnings


def configure_plan_benefit(
    *, plan: Plan, benefit: Benefit, configuration: dict[str, Any]
) -> tuple[PlanBenefit, list[dict[str, str]]]:
    """Upserts the coverage configuration of a Plan. A COMPLEMENTARY
    coverage not yet attached is attached (optional or included, per
    `configuration.inclusion`); BASE coverages are always attached and
    must stay INCLUDED. An INACTIVE coverage cannot be newly attached."""
    existing = PlanBenefit.objects.filter(plan=plan, benefit=benefit).first()
    if existing is None and benefit.status != BenefitStatus.ACTIVE.value:
        raise InvalidBenefitSelectionError(f"A cobertura '{benefit.code}' está inativa (INACTIVE) e não pode ser adicionada a um plano")
    normalised, warnings = validate_coverage_config(
        configuration,
        benefit_code=benefit.code,
        benefit_category=benefit.benefit_type,
        benefit_definition=benefit.definition_json,
        plan_settings=plan.settings_json,
    )
    before = existing.configuration_json if existing else None
    with transaction.atomic():
        if existing is None:
            plan_benefit = PlanBenefit.objects.create(
                tenant_id=plan.tenant_id, plan=plan, benefit=benefit, configuration_json=normalised
            )
        else:
            PlanBenefit.objects.filter(id=existing.id).update(configuration_json=normalised)
            plan_benefit = PlanBenefit.objects.get(id=existing.id)
    _audit.record(
        action="plan_benefit.configured",
        entity_type="PlanBenefit",
        entity_id=str(plan_benefit.id),
        metadata=change_metadata(
            before=before, after=normalised, planId=str(plan.id), benefitCode=benefit.code
        ),
    )
    return plan_benefit, warnings


def validate_plan(*, plan: Plan) -> dict[str, Any]:
    """Re-validates settings and every coverage configuration against the
    plan's *current* settings (a settings change can invalidate a coverage
    config, e.g. HOUSEHOLD_SHARED after switching the plan to GROUP) and runs
    the plan-level completeness rules. Never raises on a content problem —
    reports it, so the front can show the whole list at once."""
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    settings = plan.settings_json or {}
    try:
        _, settings_warnings = validate_plan_settings(settings)
        warnings.extend({**w, "scope": "plan.settings"} for w in settings_warnings)
    except DomainProblem as exc:
        errors.append({"code": "PLAN_SETTINGS", "message": str(exc), "scope": "plan.settings"})
    if not settings:
        warnings.append(
            {
                "code": "PLAN_SETTINGS_EMPTY",
                "message": "Plano sem definições (segmento, escalão, sistema de acesso, idades).",
                "scope": "plan.settings",
            }
        )

    coverages: list[dict[str, Any]] = []
    for plan_benefit in PlanBenefit.objects.filter(plan=plan).select_related("benefit").order_by("benefit__code"):
        benefit = plan_benefit.benefit
        coverages.append({"code": benefit.code, "category": benefit.benefit_type, "config": plan_benefit.configuration_json or {}})
        try:
            _, cov_warnings = validate_coverage_config(
                plan_benefit.configuration_json,
                benefit_code=benefit.code,
                benefit_category=benefit.benefit_type,
                benefit_definition=benefit.definition_json,
                plan_settings=settings,
            )
            warnings.extend({**w, "scope": f"coverage.{benefit.code}"} for w in cov_warnings)
        except DomainProblem as exc:
            errors.append({"code": "COVERAGE_CONFIG", "message": str(exc), "scope": f"coverage.{benefit.code}"})

    for issue in plan_completeness_issues(segment=settings.get("segment"), coverages=coverages):
        target = errors if issue["severity"] == "ERROR" else warnings
        target.append({"code": issue["code"], "message": issue["message"], "scope": "plan"})

    return {"planId": str(plan.id), "valid": not errors, "errors": errors, "warnings": warnings}


def plan_coverage_summary(*, plan: Plan) -> list[dict[str, Any]]:
    """Plain description of the plan's coverages with their resolved
    inclusion/currency — consumed by pricing (dimensions) and documents."""
    rows = []
    for pb in PlanBenefit.objects.filter(plan=plan).select_related("benefit").order_by("benefit__code"):
        config = pb.configuration_json or {}
        rows.append(
            {
                "code": pb.benefit.code,
                "name": pb.benefit.name,
                "category": pb.benefit.benefit_type,
                "inclusion": config.get("inclusion", "INCLUDED"),
                "currency": config.get("currency", "AOA"),
                "limits": config.get("limits", []),
                "participation": config.get("participation", {}),
                "waitingDays": config.get("waitingDays", {}),
                "requiresPriorApproval": bool(config.get("requiresPriorApproval", False)),
                "configuration": config,
            }
        )
    return rows

