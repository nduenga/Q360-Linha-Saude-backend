from __future__ import annotations

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

    return PublishedBusinessPricing(
        reference_premiums=configs["pricing.reference_premiums"],
        factors=configs["pricing.factors"],
        adjustments=configs["pricing.adjustments"],
        taxes_fees=configs["pricing.taxes_fees"],
        versions=versions,
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
