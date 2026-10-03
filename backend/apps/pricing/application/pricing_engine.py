"""Deterministic pricing engine (Q360-S4-02), explainability (Q360-S4-04)
and scenario simulation (Q360-S5-02).

ART-009 PricingRun state machine: REQUESTED -> CALCULATING ->
CALCULATED | FAILED (ART-012 V015 `ck_pricing_status`, enforced here by
always writing REQUESTED then CALCULATING then the terminal state in that
order, inside one transaction per run).

OPEN DECISION — see OPEN_DECISIONS.md#S04-PRICING-CONTEXT-001: ART-006's
`PricingCalculateRequest.context` is `additionalProperties: true` with no
sub-fields fixed by any artifact, and neither `Plan` nor `ProductVersion`
carries a field naming which `RatingTable`/`PricingParameterSet` applies
to it. This module therefore requires the caller to name them explicitly
inside `context` (`ratingTableCode`, `parameterSetCode`, optionally
`ruleVersionCode`, optionally `members: {<memberId>: {<dimension>: ...}}`)
— a deliberate, documented convention, not an invented business rule.

OPEN DECISION — see OPEN_DECISIONS.md#S04-ROUNDING-001 (OD-002): the
rating/rounding *mechanism* below (BASE -> chain of FACTORs, multiplying;
optional PRICING-rule ADJUSTMENTs, additive; rounded to 2dp at every step)
is this module's own documented convention for combining the generic
schema fields (BASE/FACTOR/ADJUSTMENT/FEE/TAX/TOTAL) — no artifact defines
the actuarial formula, and none is invented: `BASE_PREMIUM` and all
`RatingFactor`/`PricingRuleConfig` values are test/fixture data (same
posture as ART-013's GT-PRICE-005 "technical fixture" golden test), never
real Angolan tariffs (OD-001, still BLOCKED-SPEC).
"""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.client.infrastructure.models import InsuredMember
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.domain.commercial_adjustments import CommercialAdjustment, parse_commercial_adjustments
from apps.pricing.domain.enums import PricingComponentType, PricingRunStatus
from apps.pricing.domain.errors import (
    PricingCalculationFailedError,
    PricingConfigError,
    ReferencedEntityNotFoundError,
)
from apps.pricing.domain.money import (
    ROUNDING_POLICY_CODE,
    ROUNDING_POLICY_VERSION,
    round_amount,
)
from apps.foundation.infrastructure.models import RuleVersion
from apps.pricing.infrastructure.models import (
    PricingComponent,
    PricingRun,
    PricingScenario,
    PricingTrace,
    RatingTable,
)
from apps.product.infrastructure.models import PricingParameterSet
from apps.business_config.application.custom_rules import (
    PublishedRules,
    load_published_rules,
    person_facts,
    quote_facts,
)
from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.domain.custom_rules import apply_pricing_action, describe as describe_rule
from apps.business_config.application.pricing import (
    PublishedBusinessPricing,
    resolve_adjustments as resolve_business_adjustments,
    resolve_factors as resolve_business_factors,
    resolve_published_business_pricing,
    resolve_reference_premium,
    resolve_taxes_and_fees,
)
from apps.pricing.infrastructure.parameter_repository import resolve_decimal_parameter, resolve_pricing_parameter_set
from apps.pricing.infrastructure.rule_repository import parse_pricing_config, resolve_pricing_rule_version
from apps.pricing.application.plan_dimensions import PlanPricingContext, resolve_plan_pricing_context
from apps.pricing.application.rating_table_service import resolve_factor, resolve_rating_table
from apps.product.infrastructure.models import Plan

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()

_BASE_PREMIUM_PARAMETER_CODE = "BASE_PREMIUM"


def calculate_pricing(
    *,
    plan_id: uuid.UUID,
    effective_date: datetime.date,
    member_ids: list[uuid.UUID],
    context: dict[str, Any],
    correlation_id: str | None,
) -> PricingRun:
    request_snapshot = {
        "planId": str(plan_id),
        "effectiveDate": effective_date.isoformat(),
        "memberIds": [str(m) for m in member_ids],
        "context": context,
    }
    return _execute(request_snapshot=request_snapshot, correlation_id=correlation_id)


class _PreviewRollback(Exception):
    """Raised on purpose to roll back a preview calculation."""


def preview_pricing(
    *,
    plan_id: uuid.UUID,
    effective_date: datetime.date,
    member_ids: list[uuid.UUID],
    context: dict[str, Any],
    correlation_id: str | None,
    render,
    allow_config_overrides: bool = False,
) -> dict[str, Any]:
    """Runs the exact same calculation as `calculate_pricing` (same engine,
    same validations, same components/trace) but **persists nothing**: the
    whole run, its audit rows and outbox events are rolled back, and
    `render(pricing_run)` (called while the run still exists) produces the
    response. This is what makes "alterar parâmetros e ver o prémio
    recalculado em tempo real" safe — a preview never creates a PricingRun,
    never writes audit/outbox and never touches a Quote (R4)."""
    request_snapshot = {
        "planId": str(plan_id),
        "effectiveDate": effective_date.isoformat(),
        "memberIds": [str(m) for m in member_ids],
        "context": context,
    }
    rendered: dict[str, Any] = {}
    try:
        with transaction.atomic():
            run = _execute(
                request_snapshot=request_snapshot,
                correlation_id=correlation_id,
                allow_config_overrides=allow_config_overrides,
            )
            rendered = dict(render(run))
            raise _PreviewRollback
    except _PreviewRollback:
        pass
    return rendered


def create_pricing_scenario(
    *,
    base_pricing_run: PricingRun,
    name: str,
    overrides: dict[str, Any],
    correlation_id: str | None,
) -> PricingScenario:
    """Q360-S5-02: re-runs the calculation with `overrides` merged on top
    of the base run's original request — never mutates `base_pricing_run`
    itself ("Não altera quote oficial")."""
    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()

    merged_snapshot = dict(base_pricing_run.input_snapshot_json)
    for key in ("planId", "effectiveDate", "memberIds"):
        if key in overrides:
            merged_snapshot[key] = overrides[key]
    if "context" in overrides and isinstance(overrides["context"], dict):
        merged_snapshot["context"] = {**merged_snapshot.get("context", {}), **overrides["context"]}

    result_run = _execute(request_snapshot=merged_snapshot, correlation_id=correlation_id)

    scenario = PricingScenario.objects.create(
        tenant_id=tenant_id.value,
        base_pricing_run=base_pricing_run,
        name=name,
        input_override_json=overrides,
        result_pricing_run=result_run,
        created_by=actor.actor_id if actor else "unknown",
    )

    _audit.record(
        action="pricing_scenario.created",
        entity_type="PricingScenario",
        entity_id=str(scenario.id),
        metadata={
            "basePricingRunId": str(base_pricing_run.id),
            "resultPricingRunId": str(result_run.id),
        },
    )
    _outbox.append(
        aggregate_type="PricingScenario",
        aggregate_id=str(scenario.id),
        event_type="PRICING.SCENARIO.CREATED",
        correlation_id=correlation_id,
        payload={
            "scenarioId": str(scenario.id),
            "name": scenario.name,
            "basePricingRunId": str(base_pricing_run.id),
            "resultPricingRunId": str(result_run.id),
        },
    )
    return scenario


def get_pricing_run(pricing_run_id: uuid.UUID) -> PricingRun | None:
    return PricingRun.objects.filter(id=pricing_run_id).first()


def _execute(
    *, request_snapshot: dict[str, Any], correlation_id: str | None, allow_config_overrides: bool = False
) -> PricingRun:
    tenant_id = CurrentTenantProvider.require()

    plan_id = uuid.UUID(str(request_snapshot["planId"]))
    effective_date = datetime.date.fromisoformat(str(request_snapshot["effectiveDate"]))
    member_ids = [uuid.UUID(str(m)) for m in request_snapshot["memberIds"]]
    context: dict[str, Any] = request_snapshot.get("context") or {}

    rating_table_code = context.get("ratingTableCode")
    parameter_set_code = context.get("parameterSetCode")

    plan = Plan.objects.filter(id=plan_id).first()
    if plan is None:
        raise ReferencedEntityNotFoundError("Referenced planId does not exist for this tenant")

    # PDF "Coberturas e Capitais": plan settings, coverage capitals, the A-E
    # participation option and the optional coverages the customer chose all
    # feed the calculation (see plan_dimensions.py) — validated up front so a
    # bad selection is a 400, never a half-built PricingRun.
    plan_context = resolve_plan_pricing_context(plan=plan, selection=context.get("selection"), effective_date=effective_date)
    commercial_adjustments = parse_commercial_adjustments(context.get("adjustments"))
    pre_existing: dict[str, dict[str, Any]] = context.get("preExisting") or {}
    if not isinstance(pre_existing, dict):
        raise ReferencedEntityNotFoundError("context.preExisting must be an object keyed by memberId")

    if not member_ids:
        raise ReferencedEntityNotFoundError("memberIds must contain at least one member")
    members = list(InsuredMember.objects.filter(id__in=member_ids))
    members_by_id = {str(m.id): m for m in members}
    missing = [str(m) for m in member_ids if str(m) not in members_by_id]
    if missing:
        raise ReferencedEntityNotFoundError(f"Unknown memberIds: {', '.join(missing)}")

    # A configuração de negócio publicada é a fonte de verdade do cálculo.
    # O caminho legado só é usado para compatibilidade com cotações/integrações
    # que ainda enviam explicitamente RatingTable/PricingParameterSet.
    config_overrides: dict[str, Any] = (context.get("configOverrides") or {}) if allow_config_overrides else {}
    business_pricing: PublishedBusinessPricing | None = None
    business_reference = BusinessConfigurationResolver.get(
        "pricing.reference_premiums", effective_date=effective_date
    )

    rating_table = None
    parameter_set = None
    base_premium = None
    if business_reference is not None and not config_overrides:
        business_pricing = resolve_published_business_pricing(effective_date=effective_date)
    else:
        if not rating_table_code or not parameter_set_code:
            raise ReferencedEntityNotFoundError(
                "Sem configuração de negócio publicada (pricing.*), context.ratingTableCode e "
                "context.parameterSetCode são obrigatórios"
            )
        rating_table = resolve_rating_table(code=rating_table_code, effective_date=effective_date)
        if config_overrides.get("ratingTableId"):
            rating_table = RatingTable.objects.filter(id=config_overrides["ratingTableId"]).first()
        if rating_table is None:
            raise PricingConfigError(f"No published RatingTable '{rating_table_code}' effective on {effective_date}")
        if not rating_table.currency_code:
            raise PricingConfigError(f"RatingTable '{rating_table_code}' has no currencyCode")

        parameter_set = resolve_pricing_parameter_set(code=parameter_set_code, effective_date=effective_date)
        if config_overrides.get("parameterSetId"):
            parameter_set = PricingParameterSet.objects.filter(id=config_overrides["parameterSetId"]).first()
        if parameter_set is None:
            raise PricingConfigError(
                f"No published PricingParameterSet '{parameter_set_code}' effective on {effective_date}"
            )
        base_premium = resolve_decimal_parameter(parameter_set, _BASE_PREMIUM_PARAMETER_CODE)
        if base_premium is None:
            raise PricingConfigError(
                f"PricingParameterSet '{parameter_set_code}' has no DECIMAL parameter '{_BASE_PREMIUM_PARAMETER_CODE}'"
            )

    rule_version = None
    rule_config = None
    rule_version_code = context.get("ruleVersionCode")
    if rule_version_code:
        rule_version = resolve_pricing_rule_version(code=rule_version_code, effective_date=effective_date)
        if rule_version is None:
            raise PricingConfigError(f"No published PRICING RuleVersion '{rule_version_code}' effective on {effective_date}")
        rule_config = parse_pricing_config(rule_version)
    if config_overrides.get("ruleVersionId"):
        rule_version = RuleVersion.objects.select_related("rule_set").filter(id=config_overrides["ruleVersionId"]).first()
        if rule_version is None:
            raise PricingConfigError("configOverrides.ruleVersionId does not exist")
        rule_config = parse_pricing_config(rule_version)

    per_member_context: dict[str, dict[str, Any]] = context.get("members") or {}

    custom_rules = load_published_rules(effective_date)
    config_snapshot = dict(business_pricing.versions) if business_pricing else {}
    if custom_rules.version is not None:
        config_snapshot["rules.custom"] = custom_rules.version

    pricing_run = PricingRun.objects.create(
        tenant_id=tenant_id.value,
        plan=plan,
        rating_table=rating_table,
        parameter_set=parameter_set,
        rule_version=rule_version,
        status=PricingRunStatus.REQUESTED.value,
        effective_date=effective_date,
        currency_code=(business_pricing.currency_code if business_pricing else rating_table.currency_code),
        rounding_policy_code=ROUNDING_POLICY_CODE,
        rounding_policy_version=ROUNDING_POLICY_VERSION,
        input_snapshot_json=request_snapshot,
        business_configuration_snapshot_json=config_snapshot,
        correlation_id=correlation_id,
    )

    try:
        with transaction.atomic():
            PricingRun.objects.filter(id=pricing_run.id).update(
                status=PricingRunStatus.CALCULATING.value, started_at=timezone.now()
            )
            total_amount = _run_calculation(
                pricing_run=pricing_run,
                tenant_id=tenant_id.value,
                members=members,
                member_ids=member_ids,
                per_member_context=per_member_context,
                rating_table_code=rating_table_code,
                base_premium=base_premium,
                business_pricing=business_pricing,
                plan=plan,
                rule_config=rule_config,
                plan_context=plan_context,
                commercial_adjustments=commercial_adjustments,
                pre_existing=pre_existing,
                custom_rules=custom_rules,
            )
            PricingRun.objects.filter(id=pricing_run.id).update(
                status=PricingRunStatus.CALCULATED.value,
                total_amount=total_amount,
                completed_at=timezone.now(),
            )
    except PricingCalculationFailedError as exc:
        PricingRun.objects.filter(id=pricing_run.id).update(
            status=PricingRunStatus.FAILED.value,
            failure_code=exc.problem_code,
            failure_message_safe=str(exc),
            completed_at=timezone.now(),
        )
        _audit.record(
            action="pricing_run.failed",
            entity_type="PricingRun",
            entity_id=str(pricing_run.id),
            metadata={"result": "FAILURE", "failureCode": exc.problem_code},
        )
        _outbox.append(
            aggregate_type="PricingRun",
            aggregate_id=str(pricing_run.id),
            event_type="PRICING.FAILED",
            correlation_id=correlation_id,
            payload={
                "pricingRunId": str(pricing_run.id),
                "failureCode": exc.problem_code,
                "failureMessage": str(exc),
            },
        )
        raise

    pricing_run.refresh_from_db()
    _audit.record(
        action="pricing_run.calculated",
        entity_type="PricingRun",
        entity_id=str(pricing_run.id),
        metadata={"totalAmount": str(pricing_run.total_amount), "currencyCode": pricing_run.currency_code},
    )
    _outbox.append(
        aggregate_type="PricingRun",
        aggregate_id=str(pricing_run.id),
        event_type="PRICING.CALCULATED",
        correlation_id=correlation_id,
        payload={
            "pricingRunId": str(pricing_run.id),
            "totalAmount": str(pricing_run.total_amount),
            "currencyCode": pricing_run.currency_code,
            "productId": str(plan.product_id),
            "planId": str(plan_id),
            "effectiveDate": effective_date.isoformat(),
        },
    )
    return pricing_run


def _run_calculation(
    *,
    pricing_run: PricingRun,
    tenant_id,
    members: list[InsuredMember],
    member_ids: list[uuid.UUID],
    per_member_context: dict[str, dict[str, Any]],
    rating_table_code: str | None,
    base_premium: Decimal | None,
    business_pricing: PublishedBusinessPricing | None,
    plan: Plan,
    rule_config,
    plan_context: PlanPricingContext,
    commercial_adjustments: list[CommercialAdjustment],
    pre_existing: dict[str, dict[str, Any]],
    custom_rules: PublishedRules | None = None,
) -> Decimal:
    custom_rules = custom_rules or PublishedRules()
    members_by_id = {str(m.id): m for m in members}
    order = 0
    trace_seq = 0
    total_amount = Decimal("0")

    def trace(step_code: str, *, rule_code: str | None = None, input_data=None, output_data=None, message=None):
        nonlocal trace_seq
        PricingTrace.objects.create(
            tenant_id=tenant_id,
            pricing_run=pricing_run,
            sequence_no=trace_seq,
            step_code=step_code,
            rule_code=rule_code,
            input_json=input_data,
            output_json=output_data,
            message=message,
        )
        trace_seq += 1

    trace(
        "CONTEXT_RESOLVED",
        output_data={
            "ratingTableCode": rating_table_code,
            "basePremium": str(base_premium) if base_premium is not None else None,
            "businessConfigurationVersions": business_pricing.versions if business_pricing else {},
            "customRulesVersion": custom_rules.version,
        },
    )

    for note in plan_context.warnings:
        trace("WARNING", rule_code=note.get("code"), message=f"{note.get('scope')}: {note.get('message')}")

    priced_member_ids = {str(m) for m in member_ids}
    for adjustment in commercial_adjustments:
        if adjustment.scope == "MEMBER" and adjustment.member_id not in priced_member_ids:
            trace(
                "WARNING",
                rule_code=adjustment.code,
                message=f"Ajuste {adjustment.code} refere um membro que não faz parte do cálculo: ignorado.",
            )

    person_rules = custom_rules.pricing("PERSON")
    quote_rules = custom_rules.pricing("QUOTE")
    rule_version_no = str(custom_rules.version["versionNo"]) if custom_rules.version else None
    relationship_categories: dict[str, str] = {}
    if any(c.field == "relationship" for r in person_rules for c in r.conditions):
        from apps.client.infrastructure.models import RelationshipCode

        relationship_categories = {rc.code: rc.category for rc in RelationshipCode.objects.all()}

    # Preserve the caller's requested memberIds order for determinism
    # (same input -> same component order -> same output, S4-02 AC).
    for member_id in member_ids:
        member = members_by_id[str(member_id)]
        # Plan/selection dimensions first, the member's own values win.
        member_context = {
            **plan_context.dimensions,
            "planCode": str(plan.code),
            "planName": str(plan.name),
            **per_member_context.get(str(member_id), {}),
        }
        if business_pricing is not None:
            member_context.setdefault("age", _member_age(member, pricing_run.effective_date))

        if business_pricing is not None:
            running_amount = round_amount(
                resolve_reference_premium(
                    pricing=business_pricing,
                    plan=plan,
                    age=member_context["age"],
                )
            )
        else:
            if base_premium is None:
                raise PricingConfigError("Legacy pricing requires BASE_PREMIUM.")
            running_amount = round_amount(base_premium)
        _guard_amount(running_amount)
        PricingComponent.objects.create(
            tenant_id=tenant_id,
            pricing_run=pricing_run,
            member=member,
            component_order=order,
            component_code=_BASE_PREMIUM_PARAMETER_CODE,
            component_type=PricingComponentType.BASE.value,
            base_amount=running_amount,
            result_amount=running_amount,
        )
        trace(
            "BASE_APPLIED",
            input_data={
                "memberId": str(member_id),
                "basePremium": str(running_amount),
                "source": "BUSINESS_CONFIGURATION" if business_pricing else "PRICING_PARAMETER_SET",
            },
            output_data={"resultAmount": str(running_amount)},
        )
        order += 1

        if business_pricing is not None:
            resolved_factors = [
                (item["code"], item["factor"], item["dimension"], item["condition"])
                for item in resolve_business_factors(pricing=business_pricing, context=member_context)
            ]
        else:
            resolved_factors = []
            factor_codes = sorted(pricing_run.rating_table.factors.values_list("factor_code", flat=True).distinct())
            for factor_code in factor_codes:
                factor = resolve_factor(
                    rating_table=pricing_run.rating_table, factor_code=factor_code, context=member_context
                )
                if factor is not None:
                    resolved_factors.append((factor_code, factor.factor_value, None, None))

        for factor_code, factor_value, dimension, condition in resolved_factors:
            running_amount = round_amount(running_amount * factor_value)
            _guard_amount(running_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id,
                pricing_run=pricing_run,
                member=member,
                component_order=order,
                component_code=factor_code,
                component_type=PricingComponentType.FACTOR.value,
                factor_value=factor_value,
                result_amount=running_amount,
                source_code=(
                    f"BUSINESS_CONFIG:pricing.factors:{factor_code}"
                    if business_pricing
                    else pricing_run.rating_table.code
                ),
                source_version=(
                    str(business_pricing.versions["pricing.factors"]["versionNo"])
                    if business_pricing
                    else str(pricing_run.rating_table.version_no)
                ),
                metadata_json={"dimension": dimension, "condition": condition} if business_pricing else {},
            )
            trace(
                "FACTOR_APPLIED",
                rule_code=factor_code,
                input_data={"memberId": str(member_id), "factorValue": str(factor_value)},
                output_data={"resultAmount": str(running_amount)},
            )
            order += 1

        option = plan_context.participation_option
        if option is not None:
            # "Quanto maior a participação escolhida, menor o prémio" — the
            # A-E option's premium adjustment (a GTE-configured plan setting).
            option_factor = Decimal("1") + option.adjustment_pct / Decimal("100")
            running_amount = round_amount(running_amount * option_factor)
            _guard_amount(running_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id,
                pricing_run=pricing_run,
                member=member,
                component_order=order,
                component_code=f"PARTICIPATION_OPTION_{option.code}",
                component_type=PricingComponentType.FACTOR.value,
                factor_value=option_factor,
                result_amount=running_amount,
                source_code=pricing_run.plan.code,
                metadata_json={"participationOption": option.code, "adjustmentPct": str(option.adjustment_pct)},
            )
            trace(
                "PARTICIPATION_OPTION_APPLIED",
                rule_code=option.code,
                input_data={"memberId": str(member_id), "adjustmentPct": str(option.adjustment_pct)},
                output_data={"resultAmount": str(running_amount)},
            )
            order += 1

        for coverage_code in (() if business_pricing is not None else plan_context.optional_coverage_codes):
            loading_pct = resolve_decimal_parameter(pricing_run.parameter_set, f"COVERAGE_LOADING_{coverage_code}")
            if loading_pct is None:
                trace(
                    "WARNING",
                    rule_code=f"COVERAGE_LOADING_{coverage_code}",
                    message=(
                        f"Cobertura opcional '{coverage_code}' escolhida mas o conjunto de parâmetros "
                        f"'{pricing_run.parameter_set.code}' não define COVERAGE_LOADING_{coverage_code}: "
                        "sem custo adicional aplicado."
                    ),
                )
                continue
            loading_amount = round_amount(round_amount(base_premium) * loading_pct / Decimal("100"))
            running_amount = round_amount(running_amount + loading_amount)
            _guard_amount(running_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id,
                pricing_run=pricing_run,
                member=member,
                component_order=order,
                component_code=f"COVERAGE_{coverage_code}",
                component_type=PricingComponentType.ADJUSTMENT.value,
                adjustment_amount=loading_amount,
                result_amount=running_amount,
                source_code=f"COVERAGE:{coverage_code}",
                source_version=str(pricing_run.parameter_set.version_no),
                metadata_json={"optionalCoverage": coverage_code, "loadingPct": str(loading_pct)},
            )
            trace(
                "COVERAGE_LOADING_APPLIED",
                rule_code=coverage_code,
                input_data={"memberId": str(member_id), "loadingPct": str(loading_pct)},
                output_data={"resultAmount": str(running_amount)},
            )
            order += 1

        if business_pricing is not None:
            for adjustment in resolve_business_adjustments(
                pricing=business_pricing, context=member_context, stage="SUBSCRIPTION"
            ):
                before = running_amount
                if adjustment["type"] == "PERCENTAGE":
                    running_amount = round_amount(running_amount * (Decimal("1") + adjustment["value"] / Decimal("100")))
                else:
                    running_amount = round_amount(running_amount + adjustment["value"])
                _guard_amount(running_amount)
                PricingComponent.objects.create(
                    tenant_id=tenant_id, pricing_run=pricing_run, member=member,
                    component_order=order, component_code=adjustment["code"],
                    component_type=PricingComponentType.ADJUSTMENT.value,
                    factor_value=(Decimal("1") + adjustment["value"] / Decimal("100")) if adjustment["type"] == "PERCENTAGE" else None,
                    adjustment_amount=round_amount(running_amount - before), result_amount=running_amount,
                    source_code=f"BUSINESS_CONFIG:pricing.adjustments:{adjustment['code']}",
                    source_version=str(business_pricing.versions["pricing.adjustments"]["versionNo"]),
                )
                trace("BUSINESS_ADJUSTMENT_APPLIED", rule_code=adjustment["code"],
                      input_data={"memberId": str(member_id), "type": adjustment["type"], "value": str(adjustment["value"])},
                      output_data={"resultAmount": str(running_amount)})
                order += 1

        if person_rules:
            facts = person_facts(
                age=member_context.get("age", _member_age(member, pricing_run.effective_date)),
                members_count=len(member_ids),
                plan_code=str(plan.code),
                plan_name=str(plan.name),
                dimensions=plan_context.dimensions,
                relationship=relationship_categories.get(member.relationship_code),
            )
            for custom in person_rules:
                if not custom.matches(facts):
                    continue
                before = running_amount
                new_amount, factor = apply_pricing_action(custom, running_amount)
                running_amount = round_amount(new_amount)
                _guard_amount(running_amount)
                PricingComponent.objects.create(
                    tenant_id=tenant_id, pricing_run=pricing_run, member=member,
                    component_order=order, component_code=custom.code,
                    component_type=PricingComponentType.ADJUSTMENT.value,
                    factor_value=factor, adjustment_amount=round_amount(running_amount - before),
                    result_amount=running_amount,
                    source_code=f"BUSINESS_CONFIG:rules.custom:{custom.code}", source_version=rule_version_no,
                    metadata_json={"rule": custom.name, "message": custom.message, "action": custom.action},
                )
                trace("CUSTOM_RULE_APPLIED", rule_code=custom.code, message=describe_rule(custom),
                      input_data={"memberId": str(member_id), "action": custom.action, "value": str(custom.value)},
                      output_data={"resultAmount": str(running_amount)})
                order += 1

        if rule_config is not None:
            for adjustment in rule_config.adjustments:
                if not adjustment.matches(member_context):
                    continue
                running_amount = round_amount(running_amount + adjustment.amount)
                _guard_amount(running_amount)
                PricingComponent.objects.create(
                    tenant_id=tenant_id,
                    pricing_run=pricing_run,
                    member=member,
                    component_order=order,
                    component_code=adjustment.code,
                    component_type=PricingComponentType.ADJUSTMENT.value,
                    adjustment_amount=adjustment.amount,
                    result_amount=running_amount,
                    source_code=pricing_run.rule_version.rule_set.code if pricing_run.rule_version else None,
                    source_version=str(pricing_run.rule_version.version_no) if pricing_run.rule_version else None,
                )
                trace(
                    "ADJUSTMENT_APPLIED",
                    rule_code=adjustment.code,
                    input_data={"memberId": str(member_id), "amount": str(adjustment.amount)},
                    output_data={"resultAmount": str(running_amount)},
                )
                order += 1

        decision = pre_existing.get(str(member_id)) or {}
        if decision.get("mode") == "ACCEPTED_WITH_LOADING" and decision.get("loadingPct") is not None:
            # PDF "Aceitação com sobreprémio": coberta com agravamento do prémio.
            loading_pct = Decimal(str(decision["loadingPct"]))
            before_loading = running_amount
            running_amount = round_amount(running_amount * (Decimal("1") + loading_pct / Decimal("100")))
            _guard_amount(running_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id,
                pricing_run=pricing_run,
                member=member,
                component_order=order,
                component_code="PRE_EXISTING_LOADING",
                component_type=PricingComponentType.ADJUSTMENT.value,
                factor_value=Decimal("1") + loading_pct / Decimal("100"),
                adjustment_amount=round_amount(running_amount - before_loading),
                result_amount=running_amount,
                source_code="PRE_EXISTING_CONDITION",
                metadata_json={"mode": "ACCEPTED_WITH_LOADING", "loadingPct": str(loading_pct)},
            )
            trace(
                "PRE_EXISTING_LOADING_APPLIED",
                rule_code="PRE_EXISTING_LOADING",
                input_data={"memberId": str(member_id), "loadingPct": str(loading_pct)},
                output_data={"resultAmount": str(running_amount)},
            )
            order += 1

        for adjustment in commercial_adjustments:
            if adjustment.scope == "MEMBER" and adjustment.member_id != str(member_id):
                continue
            if adjustment.scope == "QUOTE" and not adjustment.is_percent:
                continue  # fixed quote-level amounts are applied once, on the total
            before = running_amount
            if adjustment.is_percent:
                running_amount = round_amount(running_amount * adjustment.factor())
            else:
                running_amount = round_amount(running_amount + adjustment.signed_amount())
            _guard_amount(running_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id,
                pricing_run=pricing_run,
                member=member,
                component_order=order,
                component_code=adjustment.code,
                component_type=PricingComponentType.ADJUSTMENT.value,
                factor_value=adjustment.factor() if adjustment.is_percent else None,
                adjustment_amount=round_amount(running_amount - before),
                result_amount=running_amount,
                source_code="COMMERCIAL_ADJUSTMENT",
                metadata_json={
                    "adjustmentId": adjustment.id,
                    "kind": adjustment.kind,
                    "value": str(adjustment.value),
                    "reason": adjustment.reason,
                },
            )
            trace(
                "COMMERCIAL_ADJUSTMENT_APPLIED",
                rule_code=adjustment.code,
                input_data={"memberId": str(member_id), "kind": adjustment.kind, "value": str(adjustment.value)},
                output_data={"resultAmount": str(running_amount)},
            )
            order += 1

        total_amount += running_amount

    total_amount = round_amount(total_amount)

    if quote_rules:
        facts = quote_facts(
            members_count=len(member_ids), plan_code=str(plan.code), plan_name=str(plan.name),
            dimensions=plan_context.dimensions,
        )
        for custom in quote_rules:
            if not custom.matches(facts):
                continue
            before_total = total_amount
            new_total, factor = apply_pricing_action(custom, total_amount)
            total_amount = round_amount(new_total)
            _guard_amount(total_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id, pricing_run=pricing_run, member=None, component_order=order,
                component_code=custom.code, component_type=PricingComponentType.ADJUSTMENT.value,
                factor_value=factor, adjustment_amount=round_amount(total_amount - before_total),
                result_amount=total_amount,
                source_code=f"BUSINESS_CONFIG:rules.custom:{custom.code}", source_version=rule_version_no,
                metadata_json={"rule": custom.name, "message": custom.message, "action": custom.action},
            )
            trace("CUSTOM_RULE_APPLIED", rule_code=custom.code, message=describe_rule(custom),
                  input_data={"action": custom.action, "value": str(custom.value), "scope": "QUOTE"},
                  output_data={"totalAmount": str(total_amount)})
            order += 1

    if business_pricing is not None:
        for adjustment in resolve_business_adjustments(
            pricing=business_pricing, context=plan_context.dimensions, stage="QUOTE"
        ):
            before_total = total_amount
            if adjustment["type"] == "PERCENTAGE":
                total_amount = round_amount(total_amount * (Decimal("1") + adjustment["value"] / Decimal("100")))
            else:
                total_amount = round_amount(total_amount + adjustment["value"])
            _guard_amount(total_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id, pricing_run=pricing_run, member=None, component_order=order,
                component_code=adjustment["code"], component_type=PricingComponentType.ADJUSTMENT.value,
                factor_value=(Decimal("1") + adjustment["value"] / Decimal("100")) if adjustment["type"] == "PERCENTAGE" else None,
                adjustment_amount=round_amount(total_amount - before_total), result_amount=total_amount,
                source_code=f"BUSINESS_CONFIG:pricing.adjustments:{adjustment['code']}",
                source_version=str(business_pricing.versions["pricing.adjustments"]["versionNo"]),
            )
            trace("BUSINESS_ADJUSTMENT_APPLIED", rule_code=adjustment["code"],
                  input_data={"type": adjustment["type"], "value": str(adjustment["value"]), "scope": "QUOTE"},
                  output_data={"totalAmount": str(total_amount)})
            order += 1

        for charge in resolve_taxes_and_fees(pricing=business_pricing):
            before_total = total_amount
            if charge["type"] == "PERCENTAGE":
                total_amount = round_amount(total_amount * (Decimal("1") + charge["value"] / Decimal("100")))
            else:
                total_amount = round_amount(total_amount + charge["value"])
            _guard_amount(total_amount)
            component_type = PricingComponentType.TAX.value if charge["category"] == "TAX" else PricingComponentType.FEE.value
            PricingComponent.objects.create(
                tenant_id=tenant_id, pricing_run=pricing_run, member=None, component_order=order,
                component_code=charge["code"], component_type=component_type,
                factor_value=(Decimal("1") + charge["value"] / Decimal("100")) if charge["type"] == "PERCENTAGE" else None,
                adjustment_amount=round_amount(total_amount - before_total), result_amount=total_amount,
                source_code=f"BUSINESS_CONFIG:pricing.taxes_fees:{charge['code']}",
                source_version=str(business_pricing.versions["pricing.taxes_fees"]["versionNo"]),
            )
            trace("BUSINESS_CHARGE_APPLIED", rule_code=charge["code"],
                  input_data={"type": charge["type"], "value": str(charge["value"])},
                  output_data={"totalAmount": str(total_amount)})
            order += 1

    for adjustment in commercial_adjustments:
        if adjustment.scope == "QUOTE" and not adjustment.is_percent:
            before_total = total_amount
            total_amount = round_amount(total_amount + adjustment.signed_amount())
            _guard_amount(total_amount)
            PricingComponent.objects.create(
                tenant_id=tenant_id,
                pricing_run=pricing_run,
                member=None,
                component_order=order,
                component_code=adjustment.code,
                component_type=PricingComponentType.ADJUSTMENT.value,
                adjustment_amount=round_amount(total_amount - before_total),
                result_amount=total_amount,
                source_code="COMMERCIAL_ADJUSTMENT",
                metadata_json={
                    "adjustmentId": adjustment.id,
                    "kind": adjustment.kind,
                    "value": str(adjustment.value),
                    "reason": adjustment.reason,
                },
            )
            trace(
                "COMMERCIAL_ADJUSTMENT_APPLIED",
                rule_code=adjustment.code,
                input_data={"kind": adjustment.kind, "value": str(adjustment.value), "scope": "QUOTE"},
                output_data={"totalAmount": str(total_amount)},
            )
            order += 1
    PricingComponent.objects.create(
        tenant_id=tenant_id,
        pricing_run=pricing_run,
        member=None,
        component_order=order,
        component_code="TOTAL",
        component_type=PricingComponentType.TOTAL.value,
        result_amount=total_amount,
    )
    trace("TOTAL_COMPUTED", output_data={"totalAmount": str(total_amount)})
    return total_amount


def _member_age(member: InsuredMember, reference_date: datetime.date) -> int:
    if member.date_of_birth is None:
        raise PricingConfigError(f"O membro {member.id} não tem data de nascimento para determinar a tarifa.")
    age = reference_date.year - member.date_of_birth.year
    if (reference_date.month, reference_date.day) < (member.date_of_birth.month, member.date_of_birth.day):
        age -= 1
    return age


#: `pricing_run.total_amount`/`pricing_component.*_amount` are
#: `numeric(30,8)` (ART-012 V015/V016) — up to 22 integer digits. This
#: ceiling is a deliberately conservative safety guard well inside that
#: capacity, not a business limit: catching a runaway multiplication
#: before it reaches actual column overflow (Q360-S5-03 "overflow").
_OVERFLOW_GUARD = Decimal("1000000000000")  # 10^12


def _guard_amount(amount: Decimal) -> None:
    """Q360-S5-03 validation pipeline: a negative running amount can never
    be a valid premium contribution, and an amount beyond `_OVERFLOW_GUARD`
    signals a runaway calculation (e.g. a misconfigured factor chain) —
    both fail the run rather than persist or return a bad price."""
    if amount < 0:
        raise PricingCalculationFailedError("Calculation produced a negative amount")
    if amount > _OVERFLOW_GUARD:
        raise PricingCalculationFailedError("Calculation exceeded the safety overflow guard")
