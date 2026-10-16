"""Fórmulas de tarifação configuráveis (chave `pricing.formulas`).

Forma do valor da configuração:

    {
      "parameters": [                       # constantes com nome (opcional)
        {"code": "taxa_admin", "label": "Encargos administrativos",
         "value": "0.13", "unit": "RATIO", "min": "0", "max": "1"}
      ],
      "rules": [                            # as fórmulas
        {"code": "encargos", "name": "Encargos", "description": "...",
         "purpose": "LOADING", "stage": "QUOTE", "target": "TOTAL",
         "expression": "total_amount * (1 + taxa_admin)",
         "variables": ["total_amount", "taxa_admin"],
         "order": 10, "active": true,
         "output": {"min": "0", "max": null}}
      ]
    }

- `target = "TOTAL"`: passo do cálculo. Os passos ativos correm por `order`
  (desempate pelo código) e cada um substitui o total da cotação; o valor é
  arredondado pela política monetária oficial (2 casas, meio-para-cima).
- `target = "VALUE"`: valor auxiliar com nome, que outras fórmulas podem
  usar pelo código. Não altera o prémio por si só.

Nomes que uma expressão pode usar: as variáveis do sistema da fase
(`SYSTEM_VARIABLES`), os `parameters` e os códigos das fórmulas VALUE. Um
passo TOTAL não pode ser referenciado (o seu efeito já está em
`total_amount`). Dependências circulares entre fórmulas VALUE são recusadas.

Fases (`stage`, decisão A9 de 2026-10-14):

- `PERSON`: por pessoa segura, sobre o prémio da pessoa depois das regras de
  risco (fatores, ajustes, regras «Quando… então…» por pessoa e sobreprémio
  de pré-existência) e antes dos ajustes comerciais e carregamentos.
- `QUOTE`: sobre o total da cotação, no fim (depois das taxas/encargos).

Um valor auxiliar (VALUE) pertence a uma fase e só pode ser usado por
fórmulas dessa fase, porque as variáveis do sistema são diferentes.
"""
from __future__ import annotations

import keyword
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from apps.business_config.domain.errors import InvalidConfiguration
from apps.foundation.domain import platform_inputs
from apps.foundation.domain.system_parameters import PLATFORM_CONSTANTS
from apps.business_config.domain.formula_engine import (
    ALLOWED_FUNCTIONS,
    ALLOWED_OPERATORS,
    FormulaError,
    evaluate_formula,
    explain_formula,
    parse_formula,
)

CONFIG_KEY = "pricing.formulas"

STAGES = ("PERSON", "QUOTE")  # pela ordem em que correm no cálculo
TARGETS = ("TOTAL", "VALUE")
PURPOSES = ("BASE", "LOADING", "DISCOUNT", "TAX", "ADJUSTMENT", "AUXILIARY")
UNITS = ("AMOUNT", "RATIO", "PERCENT", "FACTOR", "COUNT")

SYSTEM_VARIABLES: dict[str, dict[str, dict[str, str]]] = {
    "PERSON": {
        "person_amount": {"label": "Prémio atual da pessoa (antes desta fórmula)", "unit": "AMOUNT"},
        "person_base": {"label": "Prémio da pessoa antes de qualquer fórmula", "unit": "AMOUNT"},
        "age": {"label": "Idade da pessoa na data de efeito", "unit": "COUNT"},
        "members_count": {"label": "Número de pessoas na cotação", "unit": "COUNT"},
    },
    "QUOTE": {
        "total_amount": {"label": "Total atual da cotação (antes desta fórmula)", "unit": "AMOUNT"},
        "base_total": {"label": "Total da cotação antes de qualquer fórmula", "unit": "AMOUNT"},
        "members_count": {"label": "Número de pessoas na cotação", "unit": "COUNT"},
    }
}

MAX_FORMULAS = 50
MAX_PARAMETERS = 100
SAFETY_LIMIT = Decimal("1000000000000")

_CODE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


@dataclass(frozen=True)
class Parameter:
    code: str
    value: Decimal
    label: str = ""
    unit: str | None = None


@dataclass(frozen=True)
class Formula:
    code: str
    name: str
    expression: str
    target: str
    stage: str
    order: int
    active: bool
    variables: frozenset[str]
    description: str = ""
    purpose: str | None = None
    output_min: Decimal | None = None
    output_max: Decimal | None = None


@dataclass(frozen=True)
class FormulaSet:
    parameters: tuple[Parameter, ...] = ()
    formulas: tuple[Formula, ...] = ()
    # ordem determinística dos passos TOTAL ativos: fase, ordem, código
    steps: tuple[Formula, ...] = ()
    # dependências diretas: código -> nomes usados
    dependencies: dict[str, frozenset[str]] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        """Grafo de dependências e ordem de execução para o frontend."""
        return {
            "evaluationOrder": [f.code for f in self.steps],
            "evaluationOrderByStage": {stage: [f.code for f in self.steps_for(stage)] for stage in STAGES},
            "stages": {f.code: f.stage for f in self.formulas},
            "dependencies": {code: sorted(names) for code, names in sorted(self.dependencies.items())},
            "inactive": [f.code for f in self.formulas if not f.active],
        }

    def steps_for(self, stage: str) -> tuple[Formula, ...]:
        return tuple(f for f in self.steps if f.stage == stage)


def _decimal(raw: Any, path: str) -> Decimal:
    if isinstance(raw, bool):
        raise InvalidConfiguration(f"{path}: número inválido")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        raise InvalidConfiguration(f"{path}: número inválido") from None
    if not value.is_finite():
        raise InvalidConfiguration(f"{path}: número inválido")
    return value


def _optional_decimal(raw: Any, path: str) -> Decimal | None:
    return None if raw is None or raw == "" else _decimal(raw, path)


def _code(raw: Any, path: str) -> str:
    if not isinstance(raw, str) or not _CODE.match(raw) or keyword.iskeyword(raw):
        raise InvalidConfiguration(
            f"{path}: código inválido {raw!r} (use minúsculas, dígitos e '_', a começar por letra; máx. 60)"
        )
    if raw in ALLOWED_FUNCTIONS:
        raise InvalidConfiguration(f"{path}: '{raw}' é o nome de uma função e não pode ser usado como código")
    return raw


def _text(row: dict, key: str, path: str, *, required: bool = False, max_length: int = 500) -> str:
    raw = row.get(key)
    if raw is None or raw == "":
        if required:
            raise InvalidConfiguration(f"{path}.{key}: campo obrigatório")
        return ""
    if not isinstance(raw, str) or len(raw) > max_length:
        raise InvalidConfiguration(f"{path}.{key}: deve ser texto até {max_length} caracteres")
    return raw


def _parse_parameters(rows: Any, reserved: set[str]) -> tuple[Parameter, ...]:
    if rows is None:
        return ()
    if not isinstance(rows, list):
        raise InvalidConfiguration("parameters: deve ser uma lista")
    if len(rows) > MAX_PARAMETERS:
        raise InvalidConfiguration(f"parameters: máximo de {MAX_PARAMETERS} parâmetros")
    seen: set[str] = set()
    result = []
    for index, row in enumerate(rows):
        path = f"parameters[{index}]"
        if not isinstance(row, dict):
            raise InvalidConfiguration(f"{path}: deve ser um objeto")
        unknown = set(row) - {"code", "label", "value", "unit", "min", "max", "description"}
        if unknown:
            raise InvalidConfiguration(f"{path}: campos desconhecidos {sorted(unknown)}")
        code = _code(row.get("code"), f"{path}.code")
        if code in reserved:
            raise InvalidConfiguration(f"{path}.code: '{code}' é um nome reservado (variável do sistema ou constante do fornecedor)")
        if code in seen:
            raise InvalidConfiguration(f"{path}.code: '{code}' está duplicado")
        seen.add(code)
        if row.get("value") is None or row.get("value") == "":
            raise InvalidConfiguration(f"{path}.value: campo obrigatório")
        value = _decimal(row.get("value"), f"{path}.value")
        low = _optional_decimal(row.get("min"), f"{path}.min")
        high = _optional_decimal(row.get("max"), f"{path}.max")
        if low is not None and high is not None and high < low:
            raise InvalidConfiguration(f"{path}: max é inferior a min")
        if (low is not None and value < low) or (high is not None and value > high):
            raise InvalidConfiguration(f"{path}.value: {value} fora do intervalo permitido [{low}, {high}]")
        unit = row.get("unit")
        if unit is not None and unit not in UNITS:
            raise InvalidConfiguration(f"{path}.unit: '{unit}' inválido (permitidos: {list(UNITS)})")
        result.append(Parameter(code=code, value=value, label=_text(row, "label", path, max_length=200), unit=unit))
    return tuple(result)


def _parse_formula(row: Any, index: int) -> Formula:
    path = f"rules[{index}]"
    if not isinstance(row, dict):
        raise InvalidConfiguration(f"{path}: deve ser um objeto")
    unknown = set(row) - {
        "code", "name", "description", "purpose", "stage", "target", "expression",
        "variables", "order", "active", "output",
    }
    if unknown:
        raise InvalidConfiguration(f"{path}: campos desconhecidos {sorted(unknown)}")
    code = _code(row.get("code"), f"{path}.code")
    stage = row.get("stage", "QUOTE")
    if stage not in STAGES:
        raise InvalidConfiguration(f"{path}.stage: fase {stage!r} não suportada (permitidas: {list(STAGES)})")
    target = row.get("target", "TOTAL")
    if target not in TARGETS:
        raise InvalidConfiguration(f"{path}.target: {target!r} inválido (permitidos: {list(TARGETS)})")
    purpose = row.get("purpose")
    if purpose is not None and purpose not in PURPOSES:
        raise InvalidConfiguration(f"{path}.purpose: {purpose!r} inválido (permitidos: {list(PURPOSES)})")
    active = row.get("active", True)
    if not isinstance(active, bool):
        raise InvalidConfiguration(f"{path}.active: deve ser verdadeiro/falso")
    order = row.get("order", (index + 1) * 10)
    if isinstance(order, bool) or not isinstance(order, int) or order < 0:
        raise InvalidConfiguration(f"{path}.order: deve ser um inteiro ≥ 0")
    expression = row.get("expression")
    try:
        _tree, used = parse_formula(expression)
    except FormulaError as exc:
        raise InvalidConfiguration(f"{path}.expression ({code}): {exc}") from None
    declared = row.get("variables")
    if declared is None:
        variables = frozenset(used)
    else:
        if not isinstance(declared, list) or not all(isinstance(v, str) for v in declared):
            raise InvalidConfiguration(f"{path}.variables: deve ser uma lista de nomes")
        variables = frozenset(declared)
        undeclared = used - variables
        if undeclared:
            raise InvalidConfiguration(
                f"{path} ({code}): a expressão usa variáveis não declaradas {sorted(undeclared)}"
            )
    output = row.get("output") or {}
    if not isinstance(output, dict) or set(output) - {"min", "max"}:
        raise InvalidConfiguration(f"{path}.output: deve ser um objeto com min/max")
    low = _optional_decimal(output.get("min"), f"{path}.output.min")
    high = _optional_decimal(output.get("max"), f"{path}.output.max")
    if low is not None and high is not None and high < low:
        raise InvalidConfiguration(f"{path}.output: max é inferior a min")
    if target == "TOTAL" and low is None:
        low = Decimal(0)  # um prémio nunca pode ser negativo
    return Formula(
        code=code,
        name=_text(row, "name", path, max_length=200) or code,
        description=_text(row, "description", path, max_length=1000),
        purpose=purpose,
        expression=expression.strip(),
        target=target,
        stage=stage,
        order=order,
        active=active,
        variables=variables,
        output_min=low,
        output_max=high,
    )


def _check_cycles(values: dict[str, Formula]) -> None:
    state: dict[str, int] = {}  # 1 = a visitar, 2 = concluído

    def visit(code: str, chain: list[str]) -> None:
        if state.get(code) == 2:
            return
        if state.get(code) == 1:
            cycle = chain[chain.index(code):] + [code]
            raise InvalidConfiguration(f"Dependência circular entre fórmulas: {' -> '.join(cycle)}")
        state[code] = 1
        for name in sorted(values[code].variables):
            if name in values:
                visit(name, chain + [code])
        state[code] = 2

    for code in sorted(values):
        visit(code, [])


def parse_formula_set(value: Any) -> FormulaSet:
    """Valida o valor completo de `pricing.formulas` e devolve-o pronto a usar."""
    if not isinstance(value, dict):
        raise InvalidConfiguration("pricing.formulas: deve ser um objeto")
    unknown = set(value) - {"parameters", "rules"}
    if unknown:
        raise InvalidConfiguration(f"pricing.formulas: secções desconhecidas {sorted(unknown)} (permitidas: parameters, rules)")
    rows = value.get("rules", [])
    if not isinstance(rows, list):
        raise InvalidConfiguration("pricing.formulas.rules: deve ser uma lista")
    if len(rows) > MAX_FORMULAS:
        raise InvalidConfiguration(f"pricing.formulas.rules: máximo de {MAX_FORMULAS} fórmulas")

    # Variáveis do motor e constantes do fornecedor: nomes reservados.
    system = set().union(*(set(v) for v in SYSTEM_VARIABLES.values())) | set(PLATFORM_CONSTANTS)
    parameters = _parse_parameters(value.get("parameters"), system)
    parameter_codes = {p.code for p in parameters}
    formulas = [_parse_formula(row, index) for index, row in enumerate(rows)]

    seen: set[str] = set()
    for formula in formulas:
        if formula.code in seen:
            raise InvalidConfiguration(f"pricing.formulas: o código '{formula.code}' está duplicado")
        if formula.code in system or formula.code in parameter_codes:
            raise InvalidConfiguration(
                f"pricing.formulas: o código '{formula.code}' coincide com uma variável do sistema ou parâmetro"
            )
        seen.add(formula.code)

    values = {f.code: f for f in formulas if f.target == "VALUE"}
    totals = {f.code for f in formulas if f.target == "TOTAL"}
    for formula in formulas:
        allowed = set(SYSTEM_VARIABLES[formula.stage]) | parameter_codes | set(values) | set(PLATFORM_CONSTANTS)
        for name in sorted(formula.variables):
            if name in totals:
                current = "person_amount" if formula.stage == "PERSON" else "total_amount"
                raise InvalidConfiguration(
                    f"Fórmula '{formula.code}': '{name}' é um passo do total e não pode ser referenciado "
                    f"(use {current})"
                )
            if name in values and values[name].stage != formula.stage:
                raise InvalidConfiguration(
                    f"Fórmula '{formula.code}' (fase {formula.stage}) não pode usar '{name}', "
                    f"que é da fase {values[name].stage}"
                )
            if name not in allowed:
                raise InvalidConfiguration(f"Fórmula '{formula.code}': variável desconhecida '{name}'")
            if name in values and formula.active and not values[name].active:
                raise InvalidConfiguration(
                    f"Fórmula '{formula.code}' depende de '{name}', que está desativada"
                )
    _check_cycles(values)

    steps = tuple(sorted(
        (f for f in formulas if f.target == "TOTAL" and f.active),
        key=lambda f: (STAGES.index(f.stage), f.order, f.code),
    ))
    return FormulaSet(
        parameters=parameters,
        formulas=tuple(formulas),
        steps=steps,
        dependencies={f.code: f.variables for f in formulas},
    )


def validate_formulas(value: Any) -> None:
    parse_formula_set(value)


def _check_output(formula: Formula, result: Decimal) -> None:
    if formula.output_min is not None and result < formula.output_min:
        raise FormulaError(f"A fórmula '{formula.code}' produziu {result}, abaixo do mínimo {formula.output_min}.")
    if formula.output_max is not None and result > formula.output_max:
        raise FormulaError(f"A fórmula '{formula.code}' produziu {result}, acima do máximo {formula.output_max}.")
    if abs(result) > SAFETY_LIMIT:
        raise FormulaError(f"A fórmula '{formula.code}' excedeu o limite de segurança.")


def _system_values(stage: str, *, current: Decimal, base: Decimal, members_count: int, age: int | None) -> dict[str, Decimal]:
    if stage == "PERSON":
        if age is None:
            raise FormulaError("As fórmulas por pessoa precisam da idade da pessoa.")
        return {"person_amount": current, "person_base": base, "age": Decimal(age),
                "members_count": Decimal(members_count)}
    return {"total_amount": current, "base_total": base, "members_count": Decimal(members_count)}


def evaluate_formula_set(
    formula_set: FormulaSet,
    *,
    total_amount: Decimal,
    members_count: int,
    round_money: Callable[[Decimal], Decimal],
    stage: str = "QUOTE",
    age: int | None = None,
    explain: bool = False,
) -> dict[str, Any]:
    """Executa os passos TOTAL da fase, por ordem, e devolve o detalhe de cada um.

    `total_amount` é o valor de partida da fase: o total da cotação (QUOTE)
    ou o prémio da pessoa (PERSON, que também exige `age`).
    Erros de cálculo (divisão por zero, resultado fora do intervalo…) são
    lançados como `FormulaError`; quem chama decide como os reportar.
    `explain=True` junta a cada passo o cálculo operação a operação
    (`explanation`, e `auxiliaryExplanations` para os valores auxiliares).
    """
    if stage not in STAGES:
        raise FormulaError(f"Fase desconhecida: {stage!r}")
    parameters = {p.code: p.value for p in formula_set.parameters}
    values = {f.code: f for f in formula_set.formulas if f.target == "VALUE"}
    base_total = total_amount
    current = total_amount
    steps: list[dict[str, Any]] = []

    for formula in formula_set.steps_for(stage):
        system = _system_values(stage, current=current, base=base_total, members_count=members_count, age=age)
        cache: dict[str, Decimal] = {}
        explanations: dict[str, list[dict[str, Any]]] = {}

        def resolve(code: str) -> Decimal:
            if code not in cache:
                helper = values[code]
                cache[code] = compute(helper)
                _check_output(helper, cache[code])
            return cache[code]

        def compute(item: Formula) -> Decimal:
            scope: dict[str, Decimal] = {}
            for name in item.variables:
                if name in system:
                    scope[name] = system[name]
                elif name in parameters:
                    scope[name] = parameters[name]
                elif name in PLATFORM_CONSTANTS:
                    continue  # o avaliador lê-a do fornecedor (platform_inputs)
                else:
                    scope[name] = resolve(name)
            if not explain:
                return evaluate_formula(item.expression, scope)
            result, explanations[item.code] = explain_formula(item.expression, scope)
            return result

        before = current
        raw = compute(formula)
        current = round_money(raw)
        _check_output(formula, current)
        constants = platform_inputs.current().constants if formula.variables & set(PLATFORM_CONSTANTS) else {}
        inputs = {
            name: str(system.get(name, parameters.get(name, cache.get(name, constants.get(name)))))
            for name in sorted(formula.variables)
        }
        extra: dict[str, Any] = {}
        if explain:
            extra = {
                "explanation": explanations[formula.code],
                "auxiliaryExplanations": {code: explanations[code] for code in sorted(cache)},
            }
        steps.append(
            {
                **extra,
                "code": formula.code,
                "name": formula.name,
                "expression": formula.expression,
                "variables": inputs,
                "auxiliaryValues": {code: str(v) for code, v in sorted(cache.items())},
                "before": before,
                "rawResult": raw,
                "result": current,
                "adjustment": round_money(current - before),
            }
        )

    return {
        "baseTotal": base_total,
        "total": current,
        "steps": steps,
        "skipped": [
            {"code": f.code, "reason": "INACTIVE"}
            for f in formula_set.formulas if f.target == "TOTAL" and not f.active and f.stage == stage
        ],
    }


def formula_catalog() -> dict[str, Any]:
    """O que o editor de fórmulas do frontend pode oferecer."""
    return {
        "configKey": CONFIG_KEY,
        "stages": list(STAGES),
        "stageDescriptions": {
            "PERSON": "Por pessoa: depois das regras de risco e antes dos ajustes comerciais e carregamentos",
            "QUOTE": "Sobre o total da cotação, no fim do cálculo",
        },
        "targets": {"TOTAL": "Passo que substitui o valor da fase (prémio da pessoa ou total da cotação)",
                    "VALUE": "Valor auxiliar reutilizável (só na mesma fase)"},
        "purposes": list(PURPOSES),
        "units": list(UNITS),
        "systemVariables": {
            stage: [{"name": name, **meta} for name, meta in variables.items()]
            for stage, variables in SYSTEM_VARIABLES.items()
        },
        "functions": [{"name": name, "description": text} for name, text in ALLOWED_FUNCTIONS.items()],
        "operators": list(ALLOWED_OPERATORS),
        "limits": {"maxFormulas": MAX_FORMULAS, "maxParameters": MAX_PARAMETERS, "maxExpressionLength": 500},
        "rounding": "Cada passo TOTAL é arredondado a 2 casas, meio-para-cima (OD-006).",
    }
