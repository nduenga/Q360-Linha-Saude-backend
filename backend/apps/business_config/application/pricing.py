from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.domain.scope import is_product_scoped
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
    formulas: dict[str, Any] | None = None

    @property
    def currency_code(self) -> str:
        value = self.reference_premiums.get("currency_code")
        if not value:
            raise PricingConfigError(
                "A configuração publicada 'pricing.reference_premiums' "
                "deve definir currency_code."
            )
        return str(value).upper()


def _scope(config) -> str:
    return "PRODUCT" if is_product_scoped(config.config_key) else "TENANT"


def resolve_published_business_pricing(*, effective_date: date, product_id=None) -> PublishedBusinessPricing:
    """Tarifa publicada e vigente. Com `product_id`, cada chave resolve para
    a versão do produto, se existir, senão para a geral (`domain/scope.py`)."""
    configs: dict[str, Any] = {}
    versions: dict[str, dict[str, Any]] = {}

    for key in PRICING_KEYS:
        config = BusinessConfigurationResolver.get(key, effective_date=effective_date, product_id=product_id)
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
            "scope": _scope(config),
        }

    actuarial_model = None
    actuarial_config = BusinessConfigurationResolver.get(
        "pricing.actuarial_model", effective_date=effective_date, product_id=product_id)
    if actuarial_config is not None:
        if not actuarial_config.approved_by or not actuarial_config.published_at:
            raise PricingConfigError("O modelo atuarial precisa de aprovação explícita antes de ser usado no pricing.")
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
            "scope": _scope(actuarial_config),
        }

    
    formulas = {}
    formulas_config = BusinessConfigurationResolver.get(
        "pricing.formulas",
        effective_date=effective_date,
        product_id=product_id,
    )

    if formulas_config is not None:
        if not isinstance(formulas_config.value_json, dict):
            raise PricingConfigError(
                "A configuração 'pricing.formulas' deve ser um objecto JSON."
            )

        formulas = formulas_config.value_json

        versions["pricing.formulas"] = {
            "configurationId": str(formulas_config.id),
            "configKey": formulas_config.config_key,
            "versionNo": formulas_config.version_no,
            "effectiveFrom": formulas_config.effective_from.isoformat(),
            "effectiveTo": (
                formulas_config.effective_to.isoformat()
                if formulas_config.effective_to
                else None
            ),
            "checksum": formulas_config.checksum,
            "scope": _scope(formulas_config),
        }


    
    return PublishedBusinessPricing(
        reference_premiums=configs["pricing.reference_premiums"],
        factors=configs["pricing.factors"],
        adjustments=configs["pricing.adjustments"],
        taxes_fees=configs["pricing.taxes_fees"],
        versions=versions,
        actuarial_model=actuarial_model,
        formulas=formulas,
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
        raise PricingConfigError(f"O plano '{plan_code}' não tem mapeamento no modelo atuarial publicado.")
    segment = str(plan_mapping.get("segment", ""))
    actuarial_plan = str(plan_mapping.get("actuarial_plan", ""))
    sex = str(sex_code or "").strip().upper()
    if sex not in {"M", "F"}:
        raise PricingConfigError("O modelo atuarial SAU/SAG exige sexo M/F para cada pessoa segura.")
    age_band = "0-17" if age <= 17 else "18-35" if age <= 35 else "36-50" if age <= 50 else "51-65" if age <= 65 else ">65"

    actuarial_to_benefit: dict[str, str] = {}
    for benefit_code, actuarial_codes in model.get("coverage_code_mapping", {}).items():
        if not isinstance(actuarial_codes, list):
            raise PricingConfigError(f"Mapeamento atuarial inválido para a cobertura '{benefit_code}'.")
        for actuarial_code in actuarial_codes:
            code = str(actuarial_code)
            if code in actuarial_to_benefit:
                raise PricingConfigError(f"O código atuarial '{code}' está associado a mais de uma cobertura.")
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
            raise PricingConfigError(f"Parâmetro atuarial inválido em {rate.get('source_cell', actuarial_code)}.")

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
        raise PricingConfigError(f"O plano '{plan_code}' não tem mapeamento no modelo atuarial publicado.")
    segment = str(plan_mapping.get("segment", ""))
    loadings_by_segment = model.get("assumptions", {}).get("loadings", {})
    loadings = loadings_by_segment.get(segment)
    if not isinstance(loadings, dict):
        raise PricingConfigError(f"O modelo atuarial não define carregamentos para o segmento '{segment}'.")
    cost_sharing = _cost_sharing_adjustment(model, profile)
    if segment != "SAG":
        # Calculador!C64 para SAU: (1 + participação nos custos) × factor regional.
        # Ambos só entram quando o perfil os indica (sem valores por omissão).
        factor = Decimal("1")
        details: dict[str, Any] = {}
        region = str(profile.get("region", "")).strip()
        if region:
            region_factor = _regional_factor(model, region)
            factor *= region_factor
            details.update({"region": region, "regionFactor": str(region_factor)})
        if cost_sharing is not None:
            factor *= Decimal("1") + cost_sharing["adjustment"]
            details["costSharing"] = cost_sharing["details"]
        return {"segment": segment, "factor": factor, "volatility": Decimal(str(loadings["volatility"])), "details": details}

    if isinstance(headcount, bool) or not isinstance(headcount, int) or headcount < 1:
        raise PricingConfigError("O modelo SAG exige pelo menos um colaborador titular para calcular a tarifa.")
    industry = str(profile.get("industry", "")).strip()
    region = str(profile.get("region", "")).strip()
    adhesion = str(profile.get("adhesion", "")).strip().upper()
    if not industry or not region or adhesion not in {"MANDATORY", "VOLUNTARY"}:
        raise PricingConfigError(
            "Não foi possível calcular o preço deste plano de grupo porque faltam dados de tarifação "
            "do proponente: sector de atividade, região e tipo de adesão. Peça ao administrador "
            "para completar o perfil atuarial ou as predefinições do produto."
        )

    size_row = next((
        row for row in model.get("group_size_factors", [])
        if row.get("headcount_from") <= headcount <= row.get("headcount_to")
    ), None)
    industry_row = next((row for row in model.get("industry_factors", []) if row.get("industry") == industry), None)
    if size_row is None or industry_row is None:
        raise PricingConfigError("Headcount ou sector não correspondem às tabelas do modelo atuarial.")

    if adhesion == "MANDATORY":
        adhesion_rows = [row for row in model.get("group_participation_factors", []) if "Obrigatória" in str(row.get("rule", ""))]
        if len(adhesion_rows) != 2:
            raise PricingConfigError("A tabela atuarial deve conter os dois fatores de adesão obrigatória.")
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
            raise PricingConfigError("Não há sobretaxa atuarial para o nível de participação enviado.")
        selected_row = eligible_rows[-1]
        adhesion_factor = Decimal("1") + Decimal(str(selected_row["premium_adjustment"]))
        adhesion_details = selected_row["premium_adjustment"]

    size_adjustment = Decimal(str(size_row["premium_adjustment"]))
    industry_factor = Decimal(str(industry_row["factor"]))
    region_factor = _regional_factor(model, region)
    factor = (Decimal("1") + size_adjustment) * adhesion_factor * industry_factor * region_factor
    if cost_sharing is not None:
        factor *= Decimal("1") + cost_sharing["adjustment"]
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
            **({"costSharing": cost_sharing["details"]} if cost_sharing is not None else {}),
        },
    }


def _regional_factor(model: dict[str, Any], region: str) -> Decimal:
    """Regras_Ajustes!B104:C108 (Calculador!C60)."""
    rows = model.get("adjustment_assumptions", {}).get("regional_factors", [])
    row = next((r for r in rows if r.get("region") == region), None)
    if row is None:
        allowed = [r.get("region") for r in rows]
        raise PricingConfigError(f"A região '{region}' não existe no modelo atuarial (permitidas: {allowed}).")
    return Decimal(str(row["factor"]))


_COST_SHARING_INPUTS = (
    ("copaymentAoa", "copayment_per_visit_aoa", "Calculador!C55"),
    ("reimbursementShare", "reimbursement_share", "Calculador!C56"),
    ("outpatientDeductibleAoa", "outpatient_annual_deductible_aoa", "Calculador!C57"),
    ("inpatientDeductibleAoa", "inpatient_deductible_aoa", "Calculador!C58"),
)


def _cost_sharing_adjustment(model: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any] | None:
    """Calculador!C59 = (1+co-pag.)×(1+comparticipação)×(1+franquia amb.)×(1+franquia int.) − 1.

    Só quando `actuarialProfile.costSharing` é enviado; cada valor tem de
    existir na tabela do modelo (o Excel usa MATCH exato)."""
    raw = profile.get("costSharing")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PricingConfigError("actuarialProfile.costSharing deve ser um objecto.")
    tables = model.get("adjustment_assumptions", {}).get("cost_sharing")
    if not isinstance(tables, dict):
        raise PricingConfigError(
            "O modelo atuarial publicado não contém as tabelas de participação nos custos; "
            "publique uma versão gerada pelo seed atual (publish_actuarial_model)."
        )
    combined = Decimal("1")
    details: dict[str, Any] = {}
    for field, table_key, cell in _COST_SHARING_INPUTS:
        if raw.get(field) is None:
            raise PricingConfigError(f"actuarialProfile.costSharing.{field} é obrigatório.")
        try:
            value = Decimal(str(raw[field]))
        except InvalidOperation as exc:
            raise PricingConfigError(f"actuarialProfile.costSharing.{field} deve ser numérico.") from exc
        rows = tables.get(table_key) or []
        row = next((r for r in rows if Decimal(str(r["value"])) == value), None)
        if row is None:
            raise PricingConfigError(
                f"actuarialProfile.costSharing.{field}={value} não existe no modelo "
                f"(valores permitidos: {[r['value'] for r in rows]})."
            )
        adjustment = Decimal(str(row["adjustment"]))
        combined *= Decimal("1") + adjustment
        details[field] = {"value": str(value), "adjustment": str(adjustment), "sourceCell": row.get("source_cell"), "excel": cell}
    return {"adjustment": combined - Decimal("1"), "details": details}


def resolve_actuarial_entry_age_surcharge(*, model: dict[str, Any], age: int) -> dict[str, Any]:
    """Regras_Ajustes!B79:D83 (Calculador!J25): agravamento pela idade na 1.ª adesão (SAU)."""
    rows = sorted(
        (r for r in model.get("adjustment_assumptions", {}).get("entry_age_adjustments", []) if r.get("age_from") is not None),
        key=lambda r: r["age_from"],
    )
    row = None
    for candidate in rows:
        if candidate["age_from"] <= age:
            row = candidate
    if row is None:
        return {"surcharge": Decimal("0"), "decision": None, "ageFrom": None}
    return {"surcharge": Decimal(str(row["surcharge"])), "decision": row.get("decision"), "ageFrom": row["age_from"]}


def resolve_actuarial_commercial_discount(
    *, model: dict[str, Any], segment: str, members_count: int, profile: dict[str, Any]
) -> dict[str, Any]:
    """Calculador!C67:C70 — desconto comercial total, limitado a desc_max:
    MAX(desc_max, (1+agregado)×(1+venda cruzada)×(1+renovação) − 1).

    Agregado só em SAU (n.º de pessoas); venda cruzada e renovação sem
    sinistralidade só quando o perfil as indica."""
    assumptions = model.get("adjustment_assumptions", {})
    family = Decimal("0")
    if segment == "SAU":
        for row in sorted(assumptions.get("family_size_discounts", []), key=lambda r: r["minimum_members"]):
            if row["minimum_members"] <= members_count:
                family = Decimal(str(row["discount"]))
    cross_sell_name = str(profile.get("crossSell") or "").strip()
    cross = Decimal("0")
    if cross_sell_name:
        row = next((r for r in assumptions.get("cross_sell_discounts", []) if r.get("product") == cross_sell_name), None)
        if row is None:
            allowed = [r.get("product") for r in assumptions.get("cross_sell_discounts", [])]
            raise PricingConfigError(f"Venda cruzada '{cross_sell_name}' não existe no modelo (permitidas: {allowed}).")
        cross = Decimal(str(row["discount"]))
    renewal = Decimal("0")
    if profile.get("noClaimsRenewal") is True:
        renewal = Decimal(str(assumptions["no_claims_renewal_discount"]))
    cap = Decimal(str(assumptions.get("maximum_cumulative_discount", "-1")))
    combined = (Decimal("1") + family) * (Decimal("1") + cross) * (Decimal("1") + renewal) - Decimal("1")
    applied = max(cap, combined)
    return {
        "discount": applied,
        "details": {
            "familySizeDiscount": str(family), "membersCount": members_count,
            "crossSell": cross_sell_name or None, "crossSellDiscount": str(cross),
            "noClaimsRenewalDiscount": str(renewal),
            "uncappedDiscount": str(combined), "maximumDiscount": str(cap), "capped": applied != combined,
        },
    }


MINIMUM_PREMIUM_KEY = "product.minimum_premium"


def resolve_minimum_premium(*, plan, effective_date: date) -> dict[str, Any] | None:
    """Prémio mínimo do plano (`product.minimum_premium`): a versão do produto
    ou a geral; dentro dela, a linha sem plano e, por cima, a do plano (só os
    valores preenchidos). Sem configuração ou sem valores: None."""
    from apps.business_config.application.readers import matches_plan

    config = BusinessConfigurationResolver.get(MINIMUM_PREMIUM_KEY, effective_date=effective_date, product_id=plan.product_id)
    if config is None:
        return None
    rows = [r for r in (flatten(MINIMUM_PREMIUM_KEY, config.value_json).get("items") or []) if isinstance(r, dict)]
    values: dict[str, Decimal] = {}
    for row in sorted(rows, key=lambda r: 1 if r.get("plan") else 0):
        if not matches_plan(row.get("plan"), plan):
            continue
        for src, dst in (("annual_minimum", "annualMinimum"), ("per_person_minimum", "perPersonMinimum")):
            if row.get(src) in (None, ""):
                continue
            try:
                amount = Decimal(str(row[src]))
            except InvalidOperation as exc:
                raise PricingConfigError(f"Prémio mínimo inválido: {row!r}") from exc
            if amount < 0:
                raise PricingConfigError("O prémio mínimo não pode ser negativo.")
            values[dst] = amount
    if not values:
        return None
    return {
        **values,
        "version": {
            "configurationId": str(config.id),
            "configKey": config.config_key,
            "versionNo": config.version_no,
            "effectiveFrom": config.effective_from.isoformat(),
            "effectiveTo": config.effective_to.isoformat() if config.effective_to else None,
            "checksum": config.checksum,
            "scope": _scope(config),
        },
    }


def minimum_premium_amount(minimum: dict[str, Any], members_count: int) -> Decimal:
    """O maior entre o mínimo da apólice e o mínimo por pessoa × pessoas."""
    return max(
        minimum.get("annualMinimum") or Decimal("0"),
        (minimum.get("perPersonMinimum") or Decimal("0")) * members_count,
    )
