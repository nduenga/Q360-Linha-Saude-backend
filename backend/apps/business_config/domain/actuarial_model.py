"""Modelo atuarial configurável (chave `pricing.actuarial_model`).

O modelo é editável pela interface (como qualquer configuração: DRAFT ->
aprovação -> PUBLISHED) e importável de um Excel com a estrutura do
`Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx`. Este módulo valida a forma e os
valores numéricos que o motor usa, para que uma edição inválida seja recusada
ao gravar e nunca chegue ao cálculo, e define as opções de cálculo
(`calculation_settings`) decididas em 2026-10-14:

- `profile_defaults` (A4): valores do perfil atuarial usados quando o
  tomador não os indica. Os recomendados são os de referência do Excel
  (factor 1 / sem participação nos custos / sem desconto), por isso não
  alteram o prémio; servem para que um tomador sem perfil seja cotado.
- `entry_age_on_renewal` (A6): como tratar o agravamento da idade de adesão
  (`Regras_Ajustes!C79:C83`) numa renovação.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.domain.errors import InvalidConfiguration

CONFIG_KEY = "pricing.actuarial_model"
SEGMENTS = ("SAU", "SAG")

ENTRY_AGE_ON_RENEWAL = {
    "ORIGINAL_ENTRY_AGE": "Mantém o agravamento da idade na 1.ª adesão (recomendado)",
    "CURRENT_AGE": "Recalcula com a idade atual",
    "NOT_APPLIED": "Não aplica o agravamento em renovações",
}
ADHESION = ("MANDATORY", "VOLUNTARY")
_PROFILE_FIELDS = {"region", "industry", "adhesion", "participationRate", "crossSell", "noClaimsRenewal",
                   "costSharing"}
_COST_SHARING_FIELDS = {
    "copaymentAoa": "copayment_per_visit_aoa",
    "reimbursementShare": "reimbursement_share",
    "outpatientDeductibleAoa": "outpatient_annual_deductible_aoa",
    "inpatientDeductibleAoa": "inpatient_deductible_aoa",
}
_LOADING_FIELDS = ("volatility", "administration_expense", "acquisition_commission", "insurer_margin",
                   "stamp_duty", "arseg_levy")
_PURE_PREMIUM_FIELDS = ("frequency_per_life", "adjusted_mean_cost_aoa", "trend_factor", "mean_claim_aoa",
                        "sigma_ln", "mu_ln")

_REFERENCE_PROFILE = {
    "region": "Luanda (Grande Luanda)",
    "crossSell": "Nenhuma",
    "noClaimsRenewal": False,
    "costSharing": {"copaymentAoa": 0, "reimbursementShare": 1, "outpatientDeductibleAoa": 0,
                    "inpatientDeductibleAoa": 0},
}
RECOMMENDED_CALCULATION_SETTINGS: dict[str, Any] = {
    "profile_defaults": {
        "SAU": dict(_REFERENCE_PROFILE),
        # Comércio e Serviços e adesão obrigatória: factores de referência do Excel.
        "SAG": {**_REFERENCE_PROFILE, "industry": "Comércio e Serviços", "adhesion": "MANDATORY"},
    },
    "entry_age_on_renewal": "ORIGINAL_ENTRY_AGE",
}


def _number(raw: Any, path: str, *, minimum: Decimal | None = None, below: Decimal | None = None,
            maximum: Decimal | None = None) -> Decimal:
    if isinstance(raw, bool) or raw is None or raw == "":
        raise InvalidConfiguration(f"{path}: número obrigatório")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        raise InvalidConfiguration(f"{path}: número inválido ({raw!r})") from None
    if not value.is_finite():
        raise InvalidConfiguration(f"{path}: número inválido ({raw!r})")
    if minimum is not None and value < minimum:
        raise InvalidConfiguration(f"{path}: deve ser ≥ {minimum} (recebido {value})")
    if maximum is not None and value > maximum:
        raise InvalidConfiguration(f"{path}: deve ser ≤ {maximum} (recebido {value})")
    if below is not None and value >= below:
        raise InvalidConfiguration(f"{path}: deve ser < {below} (recebido {value})")
    return value


def _rows(value: Any, path: str, *, required: bool = True) -> list[dict[str, Any]]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value):
        raise InvalidConfiguration(f"{path}: deve ser uma lista {'não vazia' if required else ''}".strip())
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise InvalidConfiguration(f"{path}[{index}]: deve ser um objeto")
    return value


def _dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidConfiguration(f"{path}: deve ser um objeto")
    return value


def validate_actuarial_model(value: Any) -> None:
    """Forma e valores do modelo; mensagens com o caminho do campo para o editor."""
    model = _dict(value, CONFIG_KEY)
    ZERO, ONE = Decimal("0"), Decimal("1")

    mapping = _dict(model.get("plan_code_mapping"), "plan_code_mapping")
    if not mapping:
        raise InvalidConfiguration("plan_code_mapping: associe pelo menos um plano a um plano actuarial")
    for code, row in mapping.items():
        row = _dict(row, f"plan_code_mapping.{code}")
        if row.get("segment") not in SEGMENTS or not row.get("actuarial_plan"):
            raise InvalidConfiguration(f"plan_code_mapping.{code}: indique segment (SAU/SAG) e actuarial_plan")

    seen_codes: set[str] = set()
    for benefit, codes in _dict(model.get("coverage_code_mapping"), "coverage_code_mapping").items():
        if not isinstance(codes, list) or not all(isinstance(c, str) and c for c in codes):
            raise InvalidConfiguration(f"coverage_code_mapping.{benefit}: deve ser uma lista de códigos atuariais")
        repeated = seen_codes & set(codes)
        if repeated:
            raise InvalidConfiguration(f"coverage_code_mapping.{benefit}: {sorted(repeated)} já associados a outra cobertura")
        seen_codes |= set(codes)

    assumptions = _dict(model.get("assumptions"), "assumptions")
    loadings = _dict(assumptions.get("loadings"), "assumptions.loadings")
    for segment in SEGMENTS:
        row = _dict(loadings.get(segment), f"assumptions.loadings.{segment}")
        for field in _LOADING_FIELDS:
            _number(row.get(field), f"assumptions.loadings.{segment}.{field}", minimum=ZERO, below=ONE)
        commercial = sum(Decimal(str(row[f])) for f in ("administration_expense", "acquisition_commission", "insurer_margin"))
        if commercial >= ONE:
            raise InvalidConfiguration(f"assumptions.loadings.{segment}: encargos + comissão + margem têm de ser < 100 %")
    for index, row in enumerate(_rows(assumptions.get("payment_installments"), "assumptions.payment_installments")):
        path = f"assumptions.payment_installments[{index}]"
        if not isinstance(row.get("frequency"), str) or not row["frequency"].strip():
            raise InvalidConfiguration(f"{path}.frequency: obrigatório")
        _number(row.get("installments"), f"{path}.installments", minimum=ONE, maximum=Decimal("12"))
        _number(row.get("loading"), f"{path}.loading", minimum=ZERO, below=ONE)

    for index, row in enumerate(_rows(model.get("age_gender_relativities"), "age_gender_relativities")):
        for key, factor in _dict(row.get("factors"), f"age_gender_relativities[{index}].factors").items():
            _number(factor, f"age_gender_relativities[{index}].factors.{key}", minimum=ZERO)

    plan_coverages = _dict(model.get("plan_coverages"), "plan_coverages")
    for segment, rows in plan_coverages.items():
        for index, row in enumerate(_rows(rows, f"plan_coverages.{segment}")):
            if row.get("status") in ("B", "O"):
                _number(row.get("capital_sublimit_aoa"), f"plan_coverages.{segment}[{index}].capital_sublimit_aoa",
                        minimum=ZERO)

    for index, row in enumerate(_rows(model.get("reference_pure_premiums"), "reference_pure_premiums")):
        path = f"reference_pure_premiums[{index}]"
        if row.get("segment") not in SEGMENTS or not row.get("plan") or not row.get("coverage_code"):
            raise InvalidConfiguration(f"{path}: indique segment, plan e coverage_code")
        for field in _PURE_PREMIUM_FIELDS:
            positive = field in ("mean_claim_aoa", "sigma_ln")
            value = _number(row.get(field), f"{path}.{field}", minimum=None if field == "mu_ln" else ZERO)
            if positive and value <= 0:
                raise InvalidConfiguration(f"{path}.{field}: deve ser > 0")

    for index, row in enumerate(_rows(model.get("group_size_factors"), "group_size_factors")):
        path = f"group_size_factors[{index}]"
        low = _number(row.get("headcount_from"), f"{path}.headcount_from", minimum=ONE)
        high = _number(row.get("headcount_to"), f"{path}.headcount_to", minimum=ONE)
        if high < low:
            raise InvalidConfiguration(f"{path}: headcount_to é inferior a headcount_from")
        _number(row.get("premium_adjustment"), f"{path}.premium_adjustment", minimum=Decimal("-1"))
        _number(row.get("volatility"), f"{path}.volatility", minimum=ZERO, below=ONE)
    for index, row in enumerate(_rows(model.get("group_participation_factors"), "group_participation_factors")):
        _number(row.get("premium_adjustment"), f"group_participation_factors[{index}].premium_adjustment",
                minimum=Decimal("-1"))
    for index, row in enumerate(_rows(model.get("industry_factors"), "industry_factors")):
        _number(row.get("factor"), f"industry_factors[{index}].factor", minimum=ZERO)

    adjustments = _dict(model.get("adjustment_assumptions"), "adjustment_assumptions")
    for index, row in enumerate(_rows(adjustments.get("regional_factors"), "adjustment_assumptions.regional_factors")):
        _number(row.get("factor"), f"adjustment_assumptions.regional_factors[{index}].factor", minimum=ZERO)
    for name in ("entry_age_adjustments", "pre_existing_severity"):
        for index, row in enumerate(_rows(adjustments.get(name), f"adjustment_assumptions.{name}", required=False)):
            _number(row.get("surcharge"), f"adjustment_assumptions.{name}[{index}].surcharge", minimum=ZERO)
    for name in ("family_size_discounts", "cross_sell_discounts"):
        for index, row in enumerate(_rows(adjustments.get(name), f"adjustment_assumptions.{name}", required=False)):
            _number(row.get("discount"), f"adjustment_assumptions.{name}[{index}].discount",
                    minimum=Decimal("-1"), maximum=ZERO)
    for name in ("no_claims_renewal_discount", "maximum_cumulative_discount"):
        if adjustments.get(name) is not None:
            _number(adjustments[name], f"adjustment_assumptions.{name}", minimum=Decimal("-1"), maximum=ZERO)
    cost_sharing = adjustments.get("cost_sharing")
    if cost_sharing is not None:
        for table, rows in _dict(cost_sharing, "adjustment_assumptions.cost_sharing").items():
            for index, row in enumerate(_rows(rows, f"adjustment_assumptions.cost_sharing.{table}")):
                path = f"adjustment_assumptions.cost_sharing.{table}[{index}]"
                _number(row.get("value"), f"{path}.value", minimum=ZERO)
                _number(row.get("adjustment"), f"{path}.adjustment", minimum=Decimal("-1"))

    if model.get("calculation_settings") is not None:
        _validate_settings(model, _dict(model["calculation_settings"], "calculation_settings"))


def _validate_settings(model: dict[str, Any], settings: dict[str, Any]) -> None:
    unknown = set(settings) - {"profile_defaults", "entry_age_on_renewal"}
    if unknown:
        raise InvalidConfiguration(f"calculation_settings: campos desconhecidos {sorted(unknown)}")
    mode = settings.get("entry_age_on_renewal")
    if mode is not None and mode not in ENTRY_AGE_ON_RENEWAL:
        raise InvalidConfiguration(
            f"calculation_settings.entry_age_on_renewal: {mode!r} inválido (permitidos: {list(ENTRY_AGE_ON_RENEWAL)})"
        )
    defaults = settings.get("profile_defaults") or {}
    unknown = set(_dict(defaults, "calculation_settings.profile_defaults")) - set(SEGMENTS)
    if unknown:
        raise InvalidConfiguration(f"calculation_settings.profile_defaults: segmentos desconhecidos {sorted(unknown)}")
    adjustments = model.get("adjustment_assumptions") or {}
    regions = {r.get("region") for r in adjustments.get("regional_factors") or []}
    industries = {r.get("industry") for r in model.get("industry_factors") or []}
    cross_sells = {r.get("product") for r in adjustments.get("cross_sell_discounts") or []}
    for segment, profile in defaults.items():
        path = f"calculation_settings.profile_defaults.{segment}"
        profile = _dict(profile, path)
        unknown = set(profile) - _PROFILE_FIELDS
        if unknown:
            raise InvalidConfiguration(f"{path}: campos desconhecidos {sorted(unknown)}")
        _member_of(profile, "region", regions, path)
        _member_of(profile, "industry", industries, path)
        _member_of(profile, "crossSell", cross_sells, path)
        if profile.get("adhesion") is not None and profile["adhesion"] not in ADHESION:
            raise InvalidConfiguration(f"{path}.adhesion: use MANDATORY ou VOLUNTARY")
        if profile.get("participationRate") is not None:
            _number(profile["participationRate"], f"{path}.participationRate", minimum=Decimal("0"), maximum=Decimal("1"))
        if profile.get("noClaimsRenewal") is not None and not isinstance(profile["noClaimsRenewal"], bool):
            raise InvalidConfiguration(f"{path}.noClaimsRenewal: deve ser verdadeiro/falso")
        if profile.get("costSharing") is not None:
            _validate_cost_sharing(adjustments, _dict(profile["costSharing"], f"{path}.costSharing"), f"{path}.costSharing")


def _member_of(profile: dict[str, Any], field: str, allowed: set, path: str) -> None:
    if profile.get(field) is not None and profile[field] not in allowed:
        raise InvalidConfiguration(f"{path}.{field}: {profile[field]!r} não existe no modelo (permitidos: {sorted(a for a in allowed if a)})")


def _validate_cost_sharing(adjustments: dict[str, Any], raw: dict[str, Any], path: str) -> None:
    tables = adjustments.get("cost_sharing")
    if not isinstance(tables, dict):
        raise InvalidConfiguration(f"{path}: o modelo não tem as tabelas adjustment_assumptions.cost_sharing")
    unknown = set(raw) - set(_COST_SHARING_FIELDS)
    if unknown:
        raise InvalidConfiguration(f"{path}: campos desconhecidos {sorted(unknown)}")
    for field, table in _COST_SHARING_FIELDS.items():
        value = _number(raw.get(field), f"{path}.{field}", minimum=Decimal("0"))
        allowed = [Decimal(str(r.get("value"))) for r in tables.get(table) or []]
        if value not in allowed:
            raise InvalidConfiguration(f"{path}.{field}: {value} não existe na tabela (permitidos: {[str(a) for a in allowed]})")


def calculation_settings(model: dict[str, Any]) -> dict[str, Any]:
    """Opções de cálculo do modelo publicado. Um modelo publicado antes destas
    opções não as tem: mantém o comportamento estrito anterior (sem valores
    por omissão no perfil; agravamento de adesão não aplicado em renovações)."""
    settings = model.get("calculation_settings")
    if not isinstance(settings, dict):
        return {"profile_defaults": {}, "entry_age_on_renewal": "NOT_APPLIED"}
    return {
        "profile_defaults": settings.get("profile_defaults") or {},
        "entry_age_on_renewal": settings.get("entry_age_on_renewal") or "ORIGINAL_ENTRY_AGE",
    }


def profile_with_defaults(model: dict[str, Any], segment: str, profile: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Completa o perfil do tomador com os valores por omissão do segmento.
    Devolve o perfil efetivo e os campos que vieram dos valores por omissão."""
    defaults = calculation_settings(model)["profile_defaults"].get(segment) or {}
    effective = dict(profile)
    used = []
    for field, value in defaults.items():
        if effective.get(field) in (None, ""):
            effective[field] = value
            used.append(field)
    return effective, sorted(used)
