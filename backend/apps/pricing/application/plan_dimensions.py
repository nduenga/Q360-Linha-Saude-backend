"""O que o plano e a escolha do cliente acrescentam ao cálculo do prémio.

Lê `Plan.settings_json` e `PlanBenefit.configuration_json` (PDF "Coberturas e
Capitais") e devolve:

  - **dimensões** (`segment`, `tier`, `category`, `accessSystem`,
    `participationOption`, `capital.<COBERTURA>`) que se juntam ao contexto de
    cada membro. Os `RatingFactor` do GTE casam com elas por
    `dimension_json` (subconjunto do contexto) — é assim que o prémio varia
    com o escalão do plano e com os capitais **sem nenhuma tabela hardcoded**;
  - o **fator da opção de participação A–E** (`1 + premiumAdjustmentPct/100`,
    "quanto maior a participação, menor o prémio");
  - as **coberturas opcionais escolhidas** (inclusão `OPTIONAL`), cada uma com
    o parâmetro `COVERAGE_LOADING_<CÓDIGO>` (% do prémio base) do conjunto de
    parâmetros — também do GTE.

Nada aqui conhece um valor de tarifa.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.business_config.application.overlays import apply_coverage_overlay, effective_plan_settings
from apps.business_config.application.readers import BusinessSnapshot
from apps.foundation.domain.problem import DomainProblem
from apps.pricing.domain.errors import ReferencedEntityNotFoundError
from apps.product.domain.coverage_config import validate_coverage_config
from apps.product.infrastructure.models import Plan, PlanBenefit

_CAPITAL_KINDS = ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED", "BIENNIAL", "FIXED_AMOUNT")


@dataclass(frozen=True)
class ParticipationOption:
    code: str
    adjustment_pct: Decimal


@dataclass(frozen=True)
class PlanPricingContext:
    dimensions: dict[str, str] = field(default_factory=dict)
    participation_option: ParticipationOption | None = None
    optional_coverage_codes: tuple[str, ...] = ()
    selection: dict[str, Any] = field(default_factory=dict)
    # Non-blocking notes from validating "e se..." coverage overrides.
    warnings: tuple[dict[str, str], ...] = ()
    # Effective coverage rows (after "e se..." overrides) — used to compare
    # scenarios and to describe a proposal: code, name, category, inclusion,
    # whether the customer actually has it, and its configuration.
    coverages: tuple[dict[str, Any], ...] = ()


def main_capital(config: dict[str, Any]) -> str | None:
    for limit in config.get("limits", []):
        if limit.get("kind") in _CAPITAL_KINDS and limit.get("amount") is not None:
            return str(limit["amount"])
    return None


def resolve_plan_pricing_context(
    *, plan: Plan, selection: dict[str, Any] | None, effective_date: datetime.date | None = None
) -> PlanPricingContext:
    selection = selection or {}
    snapshot = BusinessSnapshot.load(effective_date)
    settings = effective_plan_settings(plan, effective_date, snapshot)
    plan_benefits = {pb.benefit.code: pb for pb in PlanBenefit.objects.filter(plan=plan).select_related("benefit")}
    coverages = {code: (pb.configuration_json or {}) for code, pb in plan_benefits.items()}
    # Configuração de negócio publicada (capitais, participação, carências...)
    # sobrepõe-se à do plano; sem ela nada muda.
    coverages, overlay_warnings = apply_coverage_overlay(
        plan=plan,
        settings=settings,
        coverages=coverages,
        benefits={c: (pb.benefit.name, pb.benefit.benefit_type, pb.benefit.definition_json) for c, pb in plan_benefits.items()},
        on=effective_date,
        snapshot=snapshot,
    )

    # "E se..." simulation (R4): replace the configuration of some coverages
    # for this calculation only — the Plan itself is never touched. Each
    # override goes through the exact same validation as a real edit.
    overrides = selection.get("coverageOverrides") or {}
    if not isinstance(overrides, dict):
        raise ReferencedEntityNotFoundError("selection.coverageOverrides tem de ser um objeto indexado pelo código da cobertura")
    normalised_overrides: dict[str, Any] = {}
    override_warnings: list[dict[str, str]] = [{**w, "scope": "businessConfig"} for w in overlay_warnings]
    for code, override in sorted(overrides.items()):
        pb = plan_benefits.get(code)
        if pb is None:
            raise ReferencedEntityNotFoundError(f"selection.coverageOverrides: '{code}' não é uma cobertura do plano '{plan.code}'")
        try:
            normalised, cov_warnings = validate_coverage_config(
                override,
                benefit_code=code,
                benefit_category=pb.benefit.benefit_type,
                benefit_definition=pb.benefit.definition_json,
                plan_settings=settings,
            )
        except DomainProblem as exc:
            raise ReferencedEntityNotFoundError(f"selection.coverageOverrides.{code}: {exc}") from exc
        coverages[code] = normalised
        normalised_overrides[code] = normalised
        override_warnings.extend({**w, "scope": f"coverageOverrides.{code}"} for w in cov_warnings)

    optional_codes = sorted(code for code, cfg in coverages.items() if cfg.get("inclusion", "INCLUDED") == "OPTIONAL")

    chosen = selection.get("optionalBenefitCodes") or []
    if not isinstance(chosen, list) or not all(isinstance(c, str) for c in chosen):
        raise ReferencedEntityNotFoundError("selection.optionalBenefitCodes tem de ser uma lista de códigos de cobertura")
    unknown = sorted(set(chosen) - set(optional_codes))
    if unknown:
        raise ReferencedEntityNotFoundError(
            f"selection.optionalBenefitCodes {unknown} não são coberturas opcionais do plano '{plan.code}' (opcionais: {optional_codes})"
        )
    chosen_codes = tuple(sorted(set(chosen)))

    dims: dict[str, str] = {}
    for key in ("segment", "tier", "category", "accessSystem"):
        if settings.get(key):
            dims[key] = str(settings[key])

    option_code = selection.get("participationOption") or settings.get("participationOption")
    option: ParticipationOption | None = None
    if option_code:
        definitions = {o["code"]: o for o in settings.get("participationOptions", [])}
        if option_code not in definitions:
            raise ReferencedEntityNotFoundError(
                f"A opção de participação '{option_code}' não está definida para o plano '{plan.code}' (definidas: {sorted(definitions)})"
            )
        option = ParticipationOption(code=option_code, adjustment_pct=Decimal(str(definitions[option_code]["premiumAdjustmentPct"])))
        dims["participationOption"] = option_code

    # capital principal de cada cobertura que o cliente efetivamente tem
    for code, config in coverages.items():
        if config.get("inclusion", "INCLUDED") == "INCLUDED" or code in chosen_codes:
            capital = main_capital(config)
            if capital is not None:
                dims[f"capital.{code}"] = capital

    details = tuple(
        {
            "code": code,
            "name": plan_benefits[code].benefit.name,
            "category": plan_benefits[code].benefit.benefit_type,
            "inclusion": config.get("inclusion", "INCLUDED"),
            "contracted": config.get("inclusion", "INCLUDED") == "INCLUDED" or code in chosen_codes,
            "configuration": config,
        }
        for code, config in sorted(coverages.items())
    )

    normalised_selection: dict[str, Any] = {}
    if normalised_overrides:
        normalised_selection["coverageOverrides"] = normalised_overrides
    if chosen_codes:
        normalised_selection["optionalBenefitCodes"] = list(chosen_codes)
    if option_code:
        normalised_selection["participationOption"] = option_code
    return PlanPricingContext(
        dimensions=dims,
        participation_option=option,
        optional_coverage_codes=chosen_codes,
        selection=normalised_selection,
        warnings=tuple(override_warnings),
        coverages=details,
    )
