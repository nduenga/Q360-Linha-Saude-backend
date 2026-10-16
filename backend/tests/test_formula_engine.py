from decimal import Decimal

import pytest

from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.formula_engine import (
    FormulaError,
    evaluate_formula,
    explain_formula,
    referenced_names,
)
from apps.business_config.domain.formulas import evaluate_formula_set, parse_formula_set
from apps.pricing.domain.money import round_amount


def test_multiplica_variaveis():
    result = evaluate_formula(
        "premio_base * factor_idade",
        {
            "premio_base": 10000,
            "factor_idade": 1.5,
        },
    )

    assert result == Decimal("15000.0")


def test_calcula_formula_com_paranteses():
    result = evaluate_formula(
        "(premio_base * factor_idade) + taxa_fixa",
        {
            "premio_base": 10000,
            "factor_idade": 1.5,
            "taxa_fixa": 500,
        },
    )

    assert result == Decimal("15500.0")


def test_arredonda_resultado():
    result = evaluate_formula(
        "round(valor / 3, 2)",
        {"valor": 100},
    )

    assert result == Decimal("33.33")


def test_arredondamento_e_meio_para_cima():
    assert evaluate_formula("round(x, 2)", {"x": "2.675"}) == Decimal("2.68")


def test_decimal_sem_erro_de_virgula_flutuante():
    assert evaluate_formula("a + b", {"a": "0.1", "b": "0.2"}) == Decimal("0.3")


def test_rejeita_variavel_inexistente():
    with pytest.raises(FormulaError):
        evaluate_formula(
            "premio_base * variavel_inexistente",
            {"premio_base": 1000},
        )


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "().__class__.__bases__",
        "x.real",
        "x[0]",
        "lambda: 1",
        "x if x else 1",
        "x > 1",
        "'texto'",
        "open('/etc/passwd')",
        "eval('1')",
        "max(*x)",
        "round(x, ndigits=2)",
        "[1, 2]",
        "x // 2",
        "x % 2",
    ],
)
def test_rejeita_codigo_arbitrario(expression):
    with pytest.raises(FormulaError):
        evaluate_formula(expression, {"x": 1})


def test_rejeita_divisao_por_zero():
    with pytest.raises(FormulaError):
        evaluate_formula("valor / 0", {"valor": 100})


def test_rejeita_expoente_excessivo():
    with pytest.raises(FormulaError):
        evaluate_formula("x ** 11", {"x": 2})


def test_rejeita_expressao_demasiado_longa_ou_complexa():
    with pytest.raises(FormulaError):
        evaluate_formula("x + " * 200 + "x", {"x": 1})


def test_extrai_variaveis_sem_avaliar():
    assert referenced_names("max(a, b) * (1 + taxa)") == {"a", "b", "taxa"}


def test_explica_o_calculo_passo_a_passo():
    result, steps = explain_formula("max(base * (1 + taxa), -minimo)", {"base": "100", "taxa": "0.1", "minimo": "-50"})
    assert result == evaluate_formula("max(base * (1 + taxa), -minimo)", {"base": "100", "taxa": "0.1", "minimo": "-50"})
    assert [(s["step"], s["expression"], s["operation"], s["operands"], s["result"]) for s in steps] == [
        (1, "base", "VARIABLE", [], "100"),
        (2, "taxa", "VARIABLE", [], "0.1"),
        (3, "1 + taxa", "+", ["1", "0.1"], "1.1"),
        (4, "base * (1 + taxa)", "*", ["100", "1.1"], "110.0"),
        (5, "minimo", "VARIABLE", [], "-50"),
        (6, "-minimo", "-", ["-50"], "50"),
        (7, "max(base * (1 + taxa), -minimo)", "max", ["110.0", "50"], "110.0"),
    ]


# ------------------------------------------------------------ conjunto de fórmulas
def _set(**overrides):
    value = {
        "parameters": [{"code": "taxa_admin", "value": "0.13", "unit": "RATIO", "min": "0", "max": "1"}],
        "rules": [
            {"code": "encargos", "name": "Encargos", "target": "VALUE",
             "expression": "base_total * taxa_admin"},
            {"code": "carregamento", "name": "Carregamento", "order": 10,
             "expression": "total_amount + encargos", "variables": ["total_amount", "encargos"]},
            {"code": "minimo", "name": "Prémio mínimo", "order": 20,
             "expression": "max(total_amount, 50 * members_count)"},
        ],
    }
    value.update(overrides)
    return value


def _run(value, total="100.00", members=1):
    return evaluate_formula_set(
        parse_formula_set(value), total_amount=Decimal(total), members_count=members, round_money=round_amount
    )


def test_passos_correm_por_ordem_com_valores_auxiliares_e_parametros():
    outcome = _run(_set())
    assert [s["code"] for s in outcome["steps"]] == ["carregamento", "minimo"]
    assert outcome["steps"][0]["result"] == Decimal("113.00")
    assert outcome["steps"][0]["auxiliaryValues"] == {"encargos": "13.0000"}  # intermédio, sem arredondar
    assert outcome["total"] == Decimal("113.00")
    # com 3 pessoas o mínimo (150) prevalece
    assert _run(_set(), members=3)["total"] == Decimal("150.00")


def test_ordem_e_deterministica_independentemente_da_posicao_na_lista():
    value = _set()
    value["rules"] = list(reversed(value["rules"]))
    assert [s["code"] for s in _run(value)["steps"]] == ["carregamento", "minimo"]


def test_formula_desativada_e_ignorada_e_registada():
    value = _set()
    value["rules"][2]["active"] = False
    outcome = _run(value, members=3)
    assert outcome["total"] == Decimal("113.00")
    assert outcome["skipped"] == [{"code": "minimo", "reason": "INACTIVE"}]


def test_resultado_de_cada_passo_e_arredondado_a_2_casas():
    value = {"rules": [{"code": "terco", "expression": "total_amount / 3"}]}
    assert _run(value)["total"] == Decimal("33.33")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({"rules": [{"code": "a", "expression": "total_amount * (1 +"}]}, "sintaxe"),
        ({"rules": [{"code": "a", "expression": "total_amount * desconhecida"}]}, "desconhecida"),
        ({"rules": [{"code": "a", "expression": "total_amount * t", "variables": ["total_amount"]}]}, "não declaradas"),
        ({"rules": [{"code": "a", "expression": "1"}, {"code": "a", "expression": "2"}]}, "duplicado"),
        ({"rules": [{"code": "Total", "expression": "1"}]}, "código inválido"),
        ({"rules": [{"code": "a", "stage": "POLICY", "expression": "1"}]}, "fase"),
        # A9: uma fórmula por pessoa não vê as variáveis da cotação nem valores de outra fase
        ({"rules": [{"code": "a", "stage": "PERSON", "expression": "total_amount * 2"}]}, "desconhecida"),
        ({"rules": [{"code": "aux", "target": "VALUE", "expression": "base_total * 0.1"},
                    {"code": "a", "stage": "PERSON", "expression": "person_amount + aux"}]}, "fase QUOTE"),
        ({"rules": [{"code": "x", "target": "VALUE", "expression": "y"},
                    {"code": "y", "target": "VALUE", "expression": "x"},
                    {"code": "t", "expression": "total_amount + x"}]}, "circular"),
        ({"rules": [{"code": "x", "target": "VALUE", "expression": "x + 1"}]}, "circular"),
        ({"rules": [{"code": "p1", "expression": "total_amount"}, {"code": "p2", "expression": "p1 * 2"}]}, "passo do total"),
        ({"rules": [{"code": "aux", "target": "VALUE", "active": False, "expression": "1"},
                    {"code": "t", "expression": "total_amount + aux"}]}, "desativada"),
        ({"parameters": [{"code": "taxa", "value": "2", "max": "1"}], "rules": []}, "fora do intervalo"),
        ({"parameters": [{"code": "total_amount", "value": "1"}], "rules": []}, "variável do sistema"),
        ({"rules": [], "outro": 1}, "desconhecidas"),
    ],
)
def test_conjunto_invalido_e_rejeitado_antes_de_publicar(value, message):
    with pytest.raises(InvalidConfiguration, match=message):
        parse_formula_set(value)


def test_intervalo_de_saida_e_verificado_no_calculo():
    value = {"rules": [{"code": "desconto", "expression": "total_amount - 500"}]}  # mínimo implícito 0
    with pytest.raises(FormulaError, match="abaixo do mínimo"):
        _run(value)
    capped = {"rules": [{"code": "teto", "expression": "total_amount * 10", "output": {"max": "500"}}]}
    with pytest.raises(FormulaError, match="acima do máximo"):
        _run(capped)


def test_analise_de_dependencias():
    analysis = parse_formula_set(_set()).describe()
    assert analysis["evaluationOrder"] == ["carregamento", "minimo"]
    assert analysis["dependencies"]["carregamento"] == ["encargos", "total_amount"]
    assert analysis["dependencies"]["encargos"] == ["base_total", "taxa_admin"]


# --- A9: fórmulas por pessoa (fase PERSON) ---------------------------------

def _person_set():
    return {
        "parameters": [{"code": "idade_limite", "value": "60"}],
        "rules": [
            {"code": "agravamento_idade", "target": "VALUE", "stage": "PERSON",
             "expression": "max(age - idade_limite, 0) * 0.01"},
            {"code": "senior", "stage": "PERSON", "order": 10,
             "expression": "person_amount * (1 + agravamento_idade)"},
            {"code": "minimo_pessoa", "stage": "PERSON", "order": 20, "expression": "max(person_amount, 50)"},
            {"code": "total", "stage": "QUOTE", "expression": "total_amount + 1"},
        ],
    }


def test_formulas_por_pessoa_correm_so_na_sua_fase_por_ordem():
    formula_set = parse_formula_set(_person_set())
    assert formula_set.describe()["evaluationOrderByStage"] == {
        "PERSON": ["senior", "minimo_pessoa"], "QUOTE": ["total"],
    }
    person = evaluate_formula_set(formula_set, total_amount=Decimal("100.00"), members_count=2,
                                  round_money=round_amount, stage="PERSON", age=65)
    assert [s["code"] for s in person["steps"]] == ["senior", "minimo_pessoa"]
    assert person["steps"][0]["result"] == Decimal("105.00")  # 5 anos acima de 60 -> +5 %
    assert person["steps"][0]["auxiliaryValues"] == {"agravamento_idade": "0.05"}
    young = evaluate_formula_set(formula_set, total_amount=Decimal("20.00"), members_count=2,
                                 round_money=round_amount, stage="PERSON", age=30)
    assert young["total"] == Decimal("50.00")  # mínimo por pessoa
    quote = _run(_person_set())
    assert [s["code"] for s in quote["steps"]] == ["total"]


def test_conjunto_explica_cada_passo_e_os_valores_auxiliares():
    outcome = evaluate_formula_set(parse_formula_set(_set()), total_amount=Decimal("100.00"), members_count=1,
                                   round_money=round_amount, explain=True)
    first = outcome["steps"][0]
    assert [s["operation"] for s in first["explanation"]] == ["VARIABLE", "VARIABLE", "+"]
    assert [s["result"] for s in first["auxiliaryExplanations"]["encargos"]] == ["100.00", "0.13", "13.0000"]
    assert "explanation" not in _run(_set())["steps"][0]  # o motor de preço não paga o custo da explicação


def test_fase_pessoa_exige_idade():
    with pytest.raises(FormulaError):
        evaluate_formula_set(parse_formula_set(_person_set()), total_amount=Decimal("1"), members_count=1,
                             round_money=round_amount, stage="PERSON")
