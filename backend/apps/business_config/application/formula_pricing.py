"""Fórmulas publicadas (`pricing.formulas`) aplicadas pelo motor de preços."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.formula_engine import FormulaError
from apps.business_config.domain.formulas import FormulaSet, evaluate_formula_set, parse_formula_set
from apps.pricing.domain.errors import PricingConfigError
from apps.pricing.domain.money import round_amount


def load_formula_set(formulas: dict) -> FormulaSet:
    """A configuração já foi validada ao ser publicada; voltar a validá-la aqui
    protege contra dados alterados fora da API."""
    try:
        return parse_formula_set(formulas)
    except InvalidConfiguration as exc:
        raise PricingConfigError(f"Configuração 'pricing.formulas' inválida: {exc}") from exc


def _evaluate(formula_set: FormulaSet, **kwargs) -> dict[str, Any]:
    try:
        return evaluate_formula_set(formula_set, round_money=round_amount, **kwargs)
    except (FormulaError, InvalidOperation) as exc:
        raise PricingConfigError(f"Erro ao aplicar 'pricing.formulas': {exc}") from exc


def apply_quote_formulas(*, formulas: dict, total_amount: Decimal, members_count: int) -> dict[str, Any]:
    """Executa as fórmulas da fase QUOTE, por ordem, sobre o total da cotação.
    Qualquer erro é um erro de configuração (o cálculo falha de forma
    explícita, nunca em silêncio)."""
    return _evaluate(load_formula_set(formulas), total_amount=total_amount, members_count=members_count)


def apply_person_formulas(
    *, formula_set: FormulaSet, person_amount: Decimal, age: int, members_count: int
) -> dict[str, Any]:
    """Executa as fórmulas da fase PERSON sobre o prémio de uma pessoa."""
    return _evaluate(formula_set, total_amount=person_amount, members_count=members_count, stage="PERSON", age=age)
