"""Regras "Quando… então…" (rules.custom): avaliação e validação sem base de dados."""
from decimal import Decimal

import pytest

from apps.business_config.application.custom_rules import person_facts, quote_facts
from apps.business_config.domain.custom_rules import apply_pricing_action, parse_rule, parse_rules, validate_rules
from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.validators import validate_structure


def _row(**over):
    row = {"name": "Maiores de 60", "active": True, "scope": "PERSON", "field": "age", "operator": "GT", "value": "60",
           "action": "INCREASE_PERCENT", "amount": "20"}
    row.update(over)
    return row


def _facts(age=61, members=3, plan="PREMIUM"):
    return person_facts(age=age, members_count=members, plan_code=plan, plan_name="Plano Premium",
                        dimensions={"segment": "GROUP", "participationOption": "B"}, relationship="SPOUSE")


def test_age_condition_and_pricing_action():
    rule = parse_rule(_row())
    assert rule.matches(_facts(61)) and not rule.matches(_facts(60))
    amount, factor = apply_pricing_action(rule, Decimal("1000"))
    assert amount == Decimal("1200") and factor == Decimal("1.2")


def test_between_is_inclusive_and_two_conditions_are_anded():
    rule = parse_rule(_row(operator="BETWEEN", value="18", value_to="30", field_2="plan", operator_2="EQ", value_2="premium"))
    assert rule.matches(_facts(18)) and rule.matches(_facts(30))
    assert not rule.matches(_facts(31)) and not rule.matches(_facts(25, plan="BASE"))


def test_plan_matches_code_or_name_and_not_equal():
    assert parse_rule(_row(field="plan", operator="EQ", value="Plano Premium")).matches(_facts())
    assert parse_rule(_row(field="plan", operator="NE", value="BASE")).matches(_facts())
    assert not parse_rule(_row(field="relationship", operator="EQ", value="CHILD")).matches(_facts())


def test_missing_fact_never_matches():
    assert not parse_rule(_row()).matches(_facts(age=None))


def test_discount_subtract_and_multiply():
    discount = parse_rule(_row(action="DISCOUNT_PERCENT", amount="10"))
    assert apply_pricing_action(discount, Decimal("1000"))[0] == Decimal("900")
    subtract = parse_rule(_row(action="SUBTRACT_AMOUNT", amount="5000"))
    assert apply_pricing_action(subtract, Decimal("1000"))[0] == Decimal("0")  # nunca negativo
    multiply = parse_rule(_row(action="MULTIPLY", amount="1.5"))
    assert apply_pricing_action(multiply, Decimal("1000"))[0] == Decimal("1500")


def test_quote_scope_facts_and_person_only_conditions():
    rule = parse_rule(_row(scope="QUOTE", field="members_count", operator="GTE", value="5", action="DISCOUNT_PERCENT", amount="5"))
    assert rule.matches(quote_facts(members_count=5, plan_code="BASE", plan_name="Base", dimensions={}))
    with pytest.raises(InvalidConfiguration, match="cotação inteira"):
        parse_rule(_row(scope="QUOTE"))  # idade é uma condição sobre a pessoa


@pytest.mark.parametrize("over,message", [
    ({"name": ""}, "nome"),
    ({"field": None, "operator": None, "value": None}, "condição"),
    ({"operator": "BETWEEN"}, "limite superior"),
    ({"value": "abc"}, "número"),
    ({"action": "NOPE"}, "o que fazer"),
    ({"amount": None}, "valor"),
    ({"action": "DISCOUNT_PERCENT", "amount": "150"}, "100"),
    ({"action": "MULTIPLY", "amount": "0"}, "anularia"),
    ({"field": "segment", "operator": "GT", "value": "GROUP"}, "igual"),
    ({"field": "segment", "operator": "EQ", "value": "X"}, "inválido"),
])
def test_invalid_rules_are_rejected_with_plain_messages(over, message):
    with pytest.raises(InvalidConfiguration, match=message):
        parse_rule(_row(**over))


def test_underwriting_actions_need_no_amount():
    rule = parse_rule(_row(action="REQUIRE_MEDICAL_REVIEW", amount=None))
    assert not rule.is_pricing and rule.value is None


def test_order_inactive_and_duplicate_codes():
    rows = [_row(name="B", order=2, code="B"), _row(name="A", order=1, code="A"), _row(name="Off", active=False, code="C")]
    assert [r.code for r in parse_rules(rows)] == ["A", "B"]
    with pytest.raises(InvalidConfiguration, match="repetido"):
        validate_rules({"rules": [_row(code="X"), _row(code="X")]})


def test_rule_attached_to_products_only_applies_to_them():
    rule = parse_rule(_row(products=["SAU"]))
    inside = person_facts(age=61, members_count=1, plan_code="BASE", plan_name="Base", dimensions={},
                          relationship=None, product=("sau", "Saúde Individual"))
    outside = person_facts(age=61, members_count=1, plan_code="BASE", plan_name="Base", dimensions={},
                           relationship=None, product=("SAG", "Saúde Grupo"))
    assert rule.matches(inside) and not rule.matches(outside)
    assert parse_rule(_row()).matches(outside)  # sem produtos = todos
    with pytest.raises(InvalidConfiguration, match="produtos"):
        parse_rule(_row(products="SAU"))


def test_field_catalog_drives_the_interface():
    from apps.business_config.domain.form_schemas import get_form_schema

    meta = get_form_schema("rules.custom")["meta"]
    assert {f["key"] for f in meta["fields"]} >= {"age", "plan", "members_count"}
    assert {a["group"] for a in meta["actions"]} == {"PRICING", "UNDERWRITING"}


def test_structure_accepts_the_form_shape_and_rejects_unknown_fields():
    validate_structure("rules.custom", {"rules": [_row(order=1)]})
    with pytest.raises(InvalidConfiguration):
        validate_structure("rules.custom", {"rules": [{**_row(), "formula": "x*2"}]})
