"""Tipos de «Taxas e Valores» da configuração por produto e regras das fórmulas."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.business_config.domain.errors import InvalidConfiguration, ProductSetupInputError
from apps.business_config.domain.product_setup import evaluate_product_setup, parse_product_setup

GROUPS = [
    {"code": "zona", "name": "Zona", "options": [{"code": "norte", "label": "Norte"}, {"code": "sul", "label": "Sul"}]},
    {"code": "risco", "name": "Risco", "options": [{"code": "baixo", "label": "Baixo"}, {"code": "alto", "label": "Alto"}]},
    {"code": "taxa", "name": "Taxa", "options": [{"code": "unica", "label": "Única"}]},
]
FIELDS = [{"code": "salarios", "label": "Número de Salários Anual", "type": "INTEGER", "min": "1", "max": "14"}]


def _value(table: dict, options=None, fields=None) -> Decimal:
    setup = parse_product_setup({"optionGroups": GROUPS, "fields": FIELDS, "values": [table],
                                 "formulas": [{"code": "resultado", "name": "R", "expression": table["group"], "unit": "FACTOR"}]})
    out = evaluate_product_setup(setup, options=options or {}, fields=fields or {}, require=False)
    return Decimal(out["results"][0]["value"])


def test_multiple_options_value_by_combination():
    table = {"group": "zona", "type": "MULTIPLE", "rows": [
        {"options": {"zona": "norte", "risco": "alto"}, "value": "1.3"},
        {"options": {"zona": "sul", "risco": "alto"}, "value": "1.1"}]}
    assert _value(table, {"zona": "norte", "risco": "alto"}) == Decimal("1.3")
    with pytest.raises(ProductSetupInputError):
        _value(table, {"zona": "norte", "risco": "baixo"})


def test_fixed_value():
    assert _value({"group": "taxa", "type": "FIXED", "value": "0.25"}) == Decimal("0.25")


def test_value_by_field_value():
    table = {"group": "taxa", "type": "FIELD_VALUE", "field": "salarios", "rows": [
        {"from": "1", "to": "12", "value": "1"}, {"from": "13", "to": "14", "value": "1.08"}]}
    assert _value(table, fields={"salarios": 14}) == Decimal("1.08")
    with pytest.raises(ProductSetupInputError):
        _value(table, fields={"salarios": 15})  # acima do máximo do campo


def test_option_conditional_value():
    table = {"group": "risco", "type": "OPTION_CONDITIONAL", "conditionGroup": "zona", "rows": [
        {"when": "norte", "option": "alto", "value": "2"}, {"when": "sul", "option": "alto", "value": "1.5"},
        {"when": "norte", "option": "baixo", "value": "1"}, {"when": "sul", "option": "baixo", "value": "0.9"}]}
    assert _value(table, {"zona": "sul", "risco": "alto"}) == Decimal("1.5")


def test_scope_and_single_premium_formula():
    setup = parse_product_setup({"optionGroups": GROUPS, "values": [{"group": "taxa", "type": "FIXED", "value": "10"}], "formulas": [
        {"code": "p_ind", "name": "Prémio individual", "expression": "taxa", "flags": {"premium": True},
         "scope": {"policyTypes": ["INDIVIDUAL"]}},
        {"code": "p_grp", "name": "Prémio grupo", "expression": "taxa * 2", "flags": {"premium": True},
         "scope": {"policyTypes": ["GROUP"]}},
        {"code": "capital", "name": "Capital", "expression": "taxa * 1000", "flags": {"capital": True}}]})
    assert evaluate_product_setup(setup, policy_type="GROUP")["premium"] == "20.00"
    assert evaluate_product_setup(setup, policy_type="INDIVIDUAL")["premium"] == "10.00"
    without_scope = parse_product_setup({"optionGroups": GROUPS, "values": [{"group": "taxa", "type": "FIXED", "value": "1"}],
                                         "formulas": [{"code": "a", "name": "A", "expression": "taxa", "flags": {"premium": True}},
                                                      {"code": "b", "name": "B", "expression": "taxa", "flags": {"premium": True}}]})
    with pytest.raises(ProductSetupInputError):
        evaluate_product_setup(without_scope)


@pytest.mark.parametrize("formula, message", [
    ({"code": "x", "name": "X", "expression": "__import__('os')"}, "não é permitida"),
    ({"code": "x", "name": "X", "expression": "zona * 2"}, "ainda não têm valores"),
    ({"code": "x", "name": "X", "expression": "1", "flags": {"premium": True, "capital": True}}, "capital"),
    ({"code": "x", "name": "X", "expression": "1", "flags": {"fractionation": True}}, "frequency"),
])
def test_invalid_formulas_are_refused(formula, message):
    with pytest.raises(InvalidConfiguration) as exc:
        parse_product_setup({"optionGroups": GROUPS, "formulas": [formula]})
    assert message in str(exc.value).lower() or message in str(exc.value)
