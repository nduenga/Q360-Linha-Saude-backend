from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.domain.shape import flatten
from apps.pricing.domain.errors import PricingConfigError


PRICING_KEYS = (
    "pricing.reference_premiums",
    "pricing.factors",
    "pricing.adjustments",
    "pricing.taxes_fees",
)


@dataclass(frozen=True)
class PublishedBusinessPricing:
    reference_premiums: dict[str, Any]
    factors: dict[str, Any]
    adjustments: dict[str, Any]
    taxes_fees: dict[str, Any]
    versions: dict[str, dict[str, Any]]
    actuarial_model: dict[str, Any] | None = None

    @property
    def currency_code(self) -> str:
        value = self.reference_premiums.get("currency_code")
        if not value:
            raise PricingConfigError(
                "A configuração publicada 'pricing.reference_premiums' deve definir currency_code."
            )
        return str(value).upper()


def resolve_published_business_pricing(*, effective_date: date) -> PublishedBusinessPricing:
    configs: dict[str, Any] = {}
    versions: dict[str, dict[str, Any]] = {}

    for key in PRICING_KEYS:
        config = BusinessConfigurationResolver.get(key, effective_date=effective_date)
        if config is None:
            raise PricingConfigError(
                f"Não existe configuração PUBLISHED '{key}' vigente em {effective_date.isoformat()}."
            )
        value = flatten(key, config.value_json)
        if not config.value_json or not isinstance(config.value_json, dict):
            raise PricingConfigError(f"A configuração '{key}' publicada deve ser um objeto JSON.")
        configs[key] = value
        versions[key] = {
            "configurationId": str(config.id),
            "configKey": config.config_key,
            "versionNo": config.version_no,
            "effectiveFrom": config.effective_from.isoformat(),
            "effectiveTo": config.effective_to.isoformat() if config.effective_to else None,
            "checksum": config.checksum,
        }

    actuarial_model = None
    actuarial_config = BusinessConfigurationResolver.get("pricing.actuarial_model", effective_date=effective_date)
    if actuarial_config is not None:
        if not actuarial_config.approved_by or not actuarial_config.published_at:
            raise PricingConfigError("O modelo actuarial precisa de aprovação explícita antes de ser usado no pricing.")
        if not isinstance(actuarial_config.value_json, dict):
            raise PricingConfigError("A configuração 'pricing.actuarial_model' deve ser um objecto JSON.")
        actuarial_model = actuarial_config.value_json
        versions["pricing.actuarial_model"] = {
            "configurationId": str(actuarial_config.id),
            "configKey": actuarial_config.config_key,
            "versionNo": actuarial_config.version_no,
            "effectiveFrom": actuarial_config.effective_from.isoformat(),
            "effectiveTo": actuarial_config.effective_to.isoformat() if actuarial_config.effective_to else None,
            "checksum": actuarial_config.checksum,
        }

    return PublishedBusinessPricing(
        reference_premiums=configs["pricing.reference_premiums"],
        factors=configs["pricing.factors"],
        adjustments=configs["pricing.adjustments"],
        taxes_fees=configs["pricing.taxes_fees"],
        versions=versions,
        actuarial_model=actuarial_model,
    )


def resolve_reference_premium(*, pricing: PublishedBusinessPricing, plan, age: int) -> Decimal:
    rows = pricing.reference_premiums.get("premiums")
    if not isinstance(rows, list) or not rows:
        raise PricingConfigError("'pricing.reference_premiums.premiums' deve conter pelo menos uma tarifa.")

    plan_keys = {str(plan.code).strip().casefold(), str(plan.name).strip().casefold()}
    matches: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        row_plan = str(row.get("plan", "")).strip().casefold()
        if row_plan not in plan_keys:
            continue
        try:
            age_from = int(row["age_from"])
            age_to = int(row["age_to"]) if row.get("age_to") not in (None, "") else None
            premium = Decimal(str(row["annual_premium"]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise PricingConfigError(f"Tarifa de referência inválida: {row!r}") from exc
        if age < age_from:
            continue
        if age_to is not None and age > age_to:
            continue
        if premium < 0:
            raise PricingConfigError(f"A tarifa anual não pode ser negativa: {row!r}")
        matches.append(row)

    if len(matches) != 1:
        raise PricingConfigError(
            f"Não foi encontrada uma única tarifa para o plano '{plan.code}' e idade {age}; "
            f"foram encontradas {len(matches)}."
        )

    return Decimal(str(matches[0]["annual_premium"]))


def resolve_factors(*, pricing: PublishedBusinessPricing, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = pricing.factors.get("factors")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise PricingConfigError("'pricing.factors.factors' deve ser uma lista.")

    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise PricingConfigError(f"Fator inválido: {row!r}")
        code = str(row.get("code", "")).strip()
        dimension = str(row.get("dimension", "")).strip()
        condition = str(row.get("condition", "")).strip()
        if not code or not dimension or not condition:
            raise PricingConfigError(f"Fator sem code/dimension/condition: {row!r}")
        if dimension not in context:
            continue
        if condition not in ("*", str(context[dimension])):
            continue
        try:
            factor = Decimal(str(row["factor"]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise PricingConfigError(f"Multiplicador inválido no fator '{code}'.") from exc
        if factor < 0:
            raise PricingConfigError(f"O multiplicador do fator '{code}' não pode ser negativo.")
        result.append({"code": code, "factor": factor, "dimension": dimension, "condition": condition})
    return result


def resolve_adjustments(*, pricing: PublishedBusinessPricing, context: dict[str, Any], stage: str) -> list[dict[str, Any]]:
    rows = pricing.adjustments.get("rules")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise PricingConfigError("'pricing.adjustments.rules' deve ser uma lista.")

    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise PricingConfigError(f"Agravamento/desconto inválido: {row!r}")
        application_stage = str(row.get("application_stage") or "").strip().upper()
        if application_stage != stage:
            continue
        try:
            value = Decimal(str(row["value"]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise PricingConfigError(f"Valor inválido no ajuste '{row.get('code', '')}'.") from exc
        kind = str(row.get("type", "")).strip().upper()
        sign = str(row.get("sign", "")).strip().upper()
        if kind not in {"PERCENTAGE", "FIXED"} or sign not in {"SURCHARGE", "DISCOUNT"}:
            raise PricingConfigError(f"Tipo/efeito inválido no ajuste '{row.get('code', '')}'.")
        max_value = row.get("max_value")
        if max_value not in (None, ""):
            try:
                maximum = Decimal(str(max_value))
            except (TypeError, InvalidOperation) as exc:
                raise PricingConfigError(f"Limite máximo inválido no ajuste '{row.get('code', '')}'.") from exc
            if maximum < 0:
                raise PricingConfigError(f"O limite máximo do ajuste '{row.get('code', '')}' não pode ser negativo.")
            value = min(value, maximum)
        signed = value if sign == "SURCHARGE" else -value
        result.append({
            "code": str(row.get("code", "")).strip(),
            "description": str(row.get("description", "")).strip(),
            "type": kind,
            "value": signed,
            "max_value": row.get("max_value"),
        })
    return result


def resolve_taxes_and_fees(*, pricing: PublishedBusinessPricing) -> list[dict[str, Any]]:
    rows = pricing.taxes_fees.get("charges")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise PricingConfigError("'pricing.taxes_fees.charges' deve ser uma lista.")

    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise PricingConfigError(f"Imposto/taxa inválido: {row!r}")
        if not bool(row.get("included_in_premium")):
            continue
        kind = str(row.get("type", "")).strip().upper()
        if kind not in {"PERCENTAGE", "FIXED"}:
            raise PricingConfigError(f"Tipo inválido no encargo '{row.get('code', '')}'.")
        try:
            value = Decimal(str(row["value"]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise PricingConfigError(f"Valor inválido no encargo '{row.get('code', '')}'.") from exc
        if value < 0:
            raise PricingConfigError(f"O encargo '{row.get('code', '')}' não pode ser negativo.")
        category = str(row.get("category", "")).strip().upper()
        if category not in {"TAX", "FEE"}:
            raise PricingConfigError(f"Categoria inválida no encargo '{row.get('code', '')}'.")
        result.append({
            "code": str(row.get("code", "")).strip(),
            "description": str(row.get("description", "")).strip(),
            "category": category,
            "type": kind,
            "value": value,
        })
    return result


def resolve_actuarial_coverage_premiums(
    *, model: dict[str, Any], plan_code: str, coverages: list[dict[str, Any]], age: int, sex_code: str
) -> list[dict[str, Any]]:
    """Resolve Excel pure premiums by contracted coverage and recalculate LEV.

    The workbook's formula uses a lognormal severity distribution. Recompute
    its limited expected value from the configured capital so a capital edit
    cannot silently reuse the workbook's old cached LEV.
    """
    plan_mapping = model.get("plan_code_mapping", {}).get(plan_code)
    if not isinstance(plan_mapping, dict):
        raise PricingConfigError(f"O plano '{plan_code}' não tem mapeamento no modelo actuarial publicado.")
    segment = str(plan_mapping.get("segment", ""))
    actuarial_plan = str(plan_mapping.get("actuarial_plan", ""))
    sex = str(sex_code or "").strip().upper()
    if sex not in {"M", "F"}:
        raise PricingConfigError("O modelo actuarial SAU/SAG exige sexo M/F para cada pessoa segura.")
    age_band = "0-17" if age <= 17 else "18-35" if age <= 35 else "36-50" if age <= 50 else "51-65" if age <= 65 else ">65"

    actuarial_to_benefit: dict[str, str] = {}
    for benefit_code, actuarial_codes in model.get("coverage_code_mapping", {}).items():
        if not isinstance(actuarial_codes, list):
            raise PricingConfigError(f"Mapeamento actuarial inválido para a cobertura '{benefit_code}'.")
        for actuarial_code in actuarial_codes:
            code = str(actuarial_code)
            if code in actuarial_to_benefit:
                raise PricingConfigError(f"O código actuarial '{code}' está associado a mais de uma cobertura.")
            actuarial_to_benefit[code] = str(benefit_code)

    contracted = {
        str(row.get("code")): row
        for row in coverages
        if isinstance(row, dict) and row.get("contracted") is True
    }
    relativities = {
        str(row.get("coverage_code")): row.get("factors", {})
        for row in model.get("age_gender_relativities", [])
        if isinstance(row, dict)
    }
    plan_coverages = {
        str(row.get("coverage_code")): row
        for row in model.get("plan_coverages", {}).get(segment, [])
        if isinstance(row, dict) and str(row.get("plan", "")).casefold() == actuarial_plan.casefold()
    }
    rates = [
        row for row in model.get("reference_pure_premiums", [])
        if isinstance(row, dict)
        and row.get("segment") == segment
        and str(row.get("plan", "")).casefold() == actuarial_plan.casefold()
    ]
    result: list[dict[str, Any]] = []
    for rate in rates:
        actuarial_code = str(rate.get("coverage_code", ""))
        benefit_code = actuarial_to_benefit.get(actuarial_code)
        if benefit_code is None or benefit_code not in contracted:
            continue
        plan_row = plan_coverages.get(actuarial_code)
        if plan_row is None or plan_row.get("status") not in {"B", "O"}:
            continue
        if rate.get("status") == "O" and not contracted[benefit_code].get("contracted"):
            continue
        try:
            factor = Decimal(str(relativities[actuarial_code][f"{sex}|{age_band}"]))
            frequency = Decimal(str(rate["frequency_per_life"]))
            adjusted_mean_cost = Decimal(str(rate["adjusted_mean_cost_aoa"]))
            trend = Decimal(str(rate["trend_factor"]))
            mean_claim = Decimal(str(rate["mean_claim_aoa"]))
            sigma = Decimal(str(rate["sigma_ln"]))
            mu = Decimal(str(rate["mu_ln"]))
            capital = Decimal(str(plan_row["capital_sublimit_aoa"]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise PricingConfigError(f"Dados actuariais incompletos em {rate.get('source_cell', actuarial_code)}.") from exc
        if factor < 0 or frequency < 0 or adjusted_mean_cost < 0 or trend < 0 or mean_claim <= 0 or sigma <= 0:
            raise PricingConfigError(f"Parâmetro actuarial inválido em {rate.get('source_cell', actuarial_code)}.")

        if capital <= 0:
            lev = Decimal("1")
        else:
            ln_capital = math.log(float(capital))
            sigma_float = float(sigma)
            first_z = (ln_capital - float(mu) - sigma_float**2) / sigma_float
            second_z = (ln_capital - float(mu)) / sigma_float
            first_cdf = (1 + math.erf(first_z / math.sqrt(2))) / 2
            second_cdf = (1 + math.erf(second_z / math.sqrt(2))) / 2
            lev = Decimal(str(first_cdf)) + capital / mean_claim * Decimal(str(1 - second_cdf))
        pure_premium = frequency * adjusted_mean_cost * trend * lev * factor
        result.append({
            "code": actuarial_code,
            "benefit_code": benefit_code,
            "age_band": age_band,
            "sex": sex,
            "relativity": factor,
            "capital": capital,
            "lev": lev,
            "pure_premium": pure_premium,
            "source_cell": rate.get("source_cell"),
        })

    if not result:
        raise PricingConfigError(
            f"Nenhuma tarifa actuarial corresponde ao plano '{plan_code}', à idade {age} e às coberturas contratadas."
        )
    return result


def resolve_actuarial_group_adjustment(
    *, model: dict[str, Any], plan_code: str, headcount: int, profile: dict[str, Any]
) -> dict[str, Any]:
    """Resolve the SAU/SAG-level loadings defined in the actuarial workbook.

    Group data is explicit: a missing industry/region/adhesion input is a
    pricing error, never silently replaced by a demo/default category.
    """
    plan_mapping = model.get("plan_code_mapping", {}).get(plan_code)
    if not isinstance(plan_mapping, dict):
        raise PricingConfigError(f"O plano '{plan_code}' não tem mapeamento no modelo actuarial publicado.")
    segment = str(plan_mapping.get("segment", ""))
    loadings_by_segment = model.get("assumptions", {}).get("loadings", {})
    loadings = loadings_by_segment.get(segment)
    if not isinstance(loadings, dict):
        raise PricingConfigError(f"O modelo actuarial não define carregamentos para o segmento '{segment}'.")
    if segment != "SAG":
        return {"segment": segment, "factor": Decimal("1"), "volatility": Decimal(str(loadings["volatility"])), "details": {}}

    if isinstance(headcount, bool) or not isinstance(headcount, int) or headcount < 1:
        raise PricingConfigError("O modelo SAG exige pelo menos um colaborador titular para calcular a tarifa.")
    industry = str(profile.get("industry", "")).strip()
    region = str(profile.get("region", "")).strip()
    adhesion = str(profile.get("adhesion", "")).strip().upper()
    if not industry or not region or adhesion not in {"MANDATORY", "VOLUNTARY"}:
        raise PricingConfigError(
            "O pricing SAG exige actuarialProfile.industry, region e adhesion (MANDATORY/VOLUNTARY)."
        )

    size_row = next((
        row for row in model.get("group_size_factors", [])
        if row.get("headcount_from") <= headcount <= row.get("headcount_to")
    ), None)
    industry_row = next((row for row in model.get("industry_factors", []) if row.get("industry") == industry), None)
    regional_rows = model.get("adjustment_assumptions", {}).get("regional_factors", [])
    region_row = next((row for row in regional_rows if row.get("region") == region), None)
    if size_row is None or industry_row is None or region_row is None:
        raise PricingConfigError("Headcount, sector ou região não correspondem às tabelas do modelo actuarial.")

    if adhesion == "MANDATORY":
        adhesion_rows = [row for row in model.get("group_participation_factors", []) if "Obrigatória" in str(row.get("rule", ""))]
        if len(adhesion_rows) != 2:
            raise PricingConfigError("A tabela actuarial deve conter os dois factores de adesão obrigatória.")
        adhesion_factor = Decimal("1")
        for row in adhesion_rows:
            adhesion_factor *= Decimal("1") + Decimal(str(row["premium_adjustment"]))
        adhesion_details = [row["premium_adjustment"] for row in adhesion_rows]
    else:
        participation = profile.get("participationRate")
        if isinstance(participation, bool) or not isinstance(participation, (str, int, float)):
            raise PricingConfigError("A adesão voluntária exige actuarialProfile.participationRate entre 0 e 1.")
        participation_rate = Decimal(str(participation))
        if participation_rate < 0 or participation_rate > 1:
            raise PricingConfigError("actuarialProfile.participationRate deve estar entre 0 e 1.")
        participation_rows = sorted(
            (row for row in model.get("group_participation_factors", []) if "Facultativa" in str(row.get("rule", ""))),
            key=lambda row: Decimal(str(row["minimum_participation"])),
        )
        eligible_rows = [row for row in participation_rows if Decimal(str(row["minimum_participation"])) <= participation_rate]
        if not eligible_rows:
            raise PricingConfigError("Não há sobretaxa actuarial para o nível de participação enviado.")
        selected_row = eligible_rows[-1]
        adhesion_factor = Decimal("1") + Decimal(str(selected_row["premium_adjustment"]))
        adhesion_details = selected_row["premium_adjustment"]

    size_adjustment = Decimal(str(size_row["premium_adjustment"]))
    industry_factor = Decimal(str(industry_row["factor"]))
    region_factor = Decimal(str(region_row["factor"]))
    factor = (Decimal("1") + size_adjustment) * adhesion_factor * industry_factor * region_factor
    volatility = Decimal(str(size_row["volatility"]))
    return {
        "segment": segment,
        "factor": factor,
        "volatility": volatility,
        "details": {
            "headcount": headcount,
            "sizeAdjustment": str(size_adjustment),
            "adhesion": adhesion,
            "adhesionAdjustment": adhesion_details,
            "industry": industry,
            "industryFactor": str(industry_factor),
            "region": region,
            "regionFactor": str(region_factor),
        },
    }
