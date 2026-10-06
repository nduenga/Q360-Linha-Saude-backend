"""Regras "Quando… então…" configuradas pelo GTE (chave `rules.custom`).

Em vez de fórmulas livres, o GTE preenche linhas de um formulário: uma
condição (campo + operador + valor, com uma segunda condição opcional) e uma
ação com linguagem de negócio. As listas abaixo são fechadas: nenhuma
expressão escrita pelo utilizador é interpretada, por isso não há execução de
código e cada regra é determinística e auditável.

Duas famílias de ação:
- tarifação: alteram o prémio (por pessoa ou no total da cotação);
- aceitação: geram um requisito/aviso/bloqueio na cotação.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from apps.business_config.domain.errors import InvalidConfiguration

CONFIG_KEY = "rules.custom"

# campo -> (rótulo, tipo, opções fechadas ou None)
FIELDS: dict[str, tuple[str, str, tuple[str, ...] | None]] = {
    "age": ("Idade da pessoa", "number", None),
    "members_count": ("Número de pessoas na cotação", "number", None),
    "plan": ("Plano", "text", None),
    "segment": ("Tipo de seguro", "choice", ("INDIVIDUAL_FAMILY", "GROUP")),
    "relationship": ("Relação com o titular", "choice", ("TITULAR", "SPOUSE", "CHILD", "ASCENDANT", "OTHER")),
    "participation_option": ("Opção de participação", "choice", ("A", "B", "C", "D", "E")),
}
FIELD_LABELS = {
    "age": "Idade da pessoa",
    "members_count": "Número de pessoas na cotação",
    "plan": "Plano",
    "segment": "Tipo de seguro",
    "relationship": "Relação com o titular",
    "participation_option": "Opção de participação (A–E)",
}
OPERATORS = ("EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN")
OPERATOR_LABELS = {
    "EQ": "é igual a",
    "NE": "é diferente de",
    "GT": "é maior que",
    "GTE": "é maior ou igual a",
    "LT": "é menor que",
    "LTE": "é menor ou igual a",
    "BETWEEN": "está entre (inclusive)",
}
SCOPES = ("PERSON", "QUOTE")
SCOPE_LABELS = {"PERSON": "Cada pessoa (calcula pessoa a pessoa)", "QUOTE": "A cotação inteira (sobre o total)"}

PRICING_ACTIONS = ("INCREASE_PERCENT", "DISCOUNT_PERCENT", "MULTIPLY", "ADD_AMOUNT", "SUBTRACT_AMOUNT")
UNDERWRITING_ACTIONS = ("REQUIRE_MEDICAL_REVIEW", "REQUIRE_TECHNICAL_REVIEW", "DECLINE", "WARN")
ACTIONS = PRICING_ACTIONS + UNDERWRITING_ACTIONS
ACTION_LABELS = {
    "INCREASE_PERCENT": "Aumentar o prémio em … %",
    "DISCOUNT_PERCENT": "Dar desconto no prémio de … %",
    "MULTIPLY": "Multiplicar o prémio por …",
    "ADD_AMOUNT": "Somar um valor fixo ao prémio",
    "SUBTRACT_AMOUNT": "Subtrair um valor fixo ao prémio",
    "REQUIRE_MEDICAL_REVIEW": "Exigir análise médica",
    "REQUIRE_TECHNICAL_REVIEW": "Enviar para análise técnica",
    "DECLINE": "Recusar (bloqueia o envio)",
    "WARN": "Mostrar apenas um aviso",
}
ACTION_UNITS = {"INCREASE_PERCENT": "%", "DISCOUNT_PERCENT": "%", "MULTIPLY": "×", "ADD_AMOUNT": "valor", "SUBTRACT_AMOUNT": "valor"}
# ações que precisam de um valor numérico
VALUE_ACTIONS = frozenset(PRICING_ACTIONS)
# ações de aceitação só fazem sentido por pessoa quando a condição é sobre a pessoa
PERSON_ONLY_FIELDS = frozenset({"age", "relationship"})


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    value: str
    value_to: str | None = None

    def matches(self, facts: Mapping[str, Any]) -> bool:
        actual = facts.get(self.field)
        if actual is None or actual == "" or actual == ():
            return False
        kind = FIELDS[self.field][1]
        if kind == "number":
            return _compare_numbers(self.operator, actual, self.value, self.value_to)
        candidates = actual if isinstance(actual, (tuple, list)) else (actual,)
        left = {str(x).strip().casefold() for x in candidates if x not in (None, "")}
        right = str(self.value).strip().casefold()
        if self.operator == "EQ":
            return right in left
        if self.operator == "NE":
            return bool(left) and right not in left
        return False


def _number(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", "."))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _compare_numbers(operator: str, actual: Any, value: Any, value_to: Any) -> bool:
    left, right = _number(actual), _number(value)
    if left is None or right is None:
        return False
    if operator == "EQ":
        return left == right
    if operator == "NE":
        return left != right
    if operator == "GT":
        return left > right
    if operator == "GTE":
        return left >= right
    if operator == "LT":
        return left < right
    if operator == "LTE":
        return left <= right
    if operator == "BETWEEN":
        upper = _number(value_to)
        return upper is not None and right <= left <= upper
    return False


@dataclass(frozen=True)
class CustomRule:
    code: str
    name: str
    scope: str
    conditions: tuple[Condition, ...]
    action: str
    value: Decimal | None
    message: str
    order: int
    products: tuple[str, ...] = ()

    def applies_to_product(self, facts: Mapping[str, Any]) -> bool:
        """Sem produtos escolhidos, a regra vale para todos."""
        if not self.products:
            return True
        wanted = {p.casefold() for p in self.products}
        actual = facts.get("product") or ()
        return any(str(x).strip().casefold() in wanted for x in actual if x)

    def matches(self, facts: Mapping[str, Any]) -> bool:
        return self.applies_to_product(facts) and all(c.matches(facts) for c in self.conditions)

    @property
    def is_pricing(self) -> bool:
        return self.action in PRICING_ACTIONS


def _present(raw: Any) -> bool:
    return raw is not None and str(raw).strip() != ""


def _condition(row: Mapping[str, Any], suffix: str, path: str) -> Condition | None:
    field = row.get(f"field{suffix}")
    operator = row.get(f"operator{suffix}")
    value = row.get(f"value{suffix}")
    value_to = row.get(f"value_to{suffix}")
    if not any(_present(x) for x in (field, operator, value, value_to)):
        return None
    if field not in FIELDS:
        raise InvalidConfiguration(f"{path}: escolha o campo da condição")
    if operator not in OPERATORS:
        raise InvalidConfiguration(f"{path}: escolha como comparar ({FIELD_LABELS[field]})")
    if not _present(value):
        raise InvalidConfiguration(f"{path}: indique o valor da condição ({FIELD_LABELS[field]})")
    _, kind, options = FIELDS[field]
    if kind == "number":
        if _number(value) is None:
            raise InvalidConfiguration(f"{path}: '{FIELD_LABELS[field]}' deve ser comparado com um número")
        if operator == "BETWEEN":
            upper = _number(value_to)
            if upper is None:
                raise InvalidConfiguration(f"{path}: indique o limite superior do intervalo ({FIELD_LABELS[field]})")
            if upper < _number(value):
                raise InvalidConfiguration(f"{path}: o limite superior é inferior ao inferior ({FIELD_LABELS[field]})")
    else:
        if operator not in ("EQ", "NE"):
            raise InvalidConfiguration(f"{path}: '{FIELD_LABELS[field]}' só pode ser 'é igual a' ou 'é diferente de'")
        if options and str(value) not in options:
            raise InvalidConfiguration(f"{path}: valor '{value}' inválido para '{FIELD_LABELS[field]}' (permitidos: {list(options)})")
    return Condition(field, operator, str(value).strip(), str(value_to).strip() if _present(value_to) else None)


def parse_rule(row: Mapping[str, Any], index: int = 0) -> CustomRule:
    path = f"rules[{index}]"
    name = str(row.get("name") or "").strip()
    if not name:
        raise InvalidConfiguration(f"{path}: dê um nome à regra")
    scope = row.get("scope") or "PERSON"
    if scope not in SCOPES:
        raise InvalidConfiguration(f"{path} ({name}): 'Aplica-se a' inválido")
    action = row.get("action")
    if action not in ACTIONS:
        raise InvalidConfiguration(f"{path} ({name}): escolha o que fazer quando a condição se verificar")
    conditions = tuple(c for c in (_condition(row, "", f"{path} ({name})"), _condition(row, "_2", f"{path} ({name})")) if c)
    if not conditions:
        raise InvalidConfiguration(f"{path} ({name}): defina pelo menos uma condição (ex.: Idade é maior que 60)")
    if scope == "QUOTE":
        bad = [FIELD_LABELS[c.field] for c in conditions if c.field in PERSON_ONLY_FIELDS]
        if bad:
            raise InvalidConfiguration(
                f"{path} ({name}): para a cotação inteira não pode usar condições sobre a pessoa ({', '.join(bad)}); "
                "use 'Cada pessoa'"
            )
    value: Decimal | None = None
    if action in VALUE_ACTIONS:
        value = _number(row.get("amount"))
        if value is None or value < 0:
            raise InvalidConfiguration(f"{path} ({name}): indique o valor (número ≥ 0) da ação")
        if action == "DISCOUNT_PERCENT" and value > 100:
            raise InvalidConfiguration(f"{path} ({name}): o desconto não pode passar de 100 %")
        if action == "MULTIPLY" and value == 0:
            raise InvalidConfiguration(f"{path} ({name}): multiplicar por 0 anularia o prémio")
    order = row.get("order")
    try:
        order_value = int(order) if _present(order) else index + 1
    except (TypeError, ValueError):
        raise InvalidConfiguration(f"{path} ({name}): a ordem deve ser um número inteiro") from None
    products = row.get("products") or []
    if not isinstance(products, list) or not all(isinstance(p, str) for p in products):
        raise InvalidConfiguration(f"{path} ({name}): os produtos devem ser uma lista de códigos")
    return CustomRule(
        products=tuple(p.strip() for p in products if p.strip()),
        code=str(row.get("code") or f"RULE_{index + 1}").strip() or f"RULE_{index + 1}",
        name=name,
        scope=scope,
        conditions=conditions,
        action=action,
        value=value,
        message=str(row.get("message") or "").strip(),
        order=order_value,
    )


def parse_rules(rows: Any, *, only_active: bool = True) -> list[CustomRule]:
    """Regras ordenadas (pela coluna Ordem; empate: posição na tabela)."""
    if not isinstance(rows, list):
        return []
    parsed: list[tuple[int, int, CustomRule]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        if only_active and row.get("active") is False:
            continue
        rule = parse_rule(row, index)
        parsed.append((rule.order, index, rule))
    return [rule for _, _, rule in sorted(parsed, key=lambda t: (t[0], t[1]))]


def validate_rules(value: Mapping[str, Any]) -> None:
    rows = value.get("rules")
    if rows is None:
        return
    codes: set[str] = set()
    for index, row in enumerate(rows):
        rule = parse_rule(row, index)
        if rule.code in codes:
            raise InvalidConfiguration(f"rules[{index}] ({rule.name}): o código '{rule.code}' está repetido")
        codes.add(rule.code)


def apply_pricing_action(rule: CustomRule, amount: Decimal) -> tuple[Decimal, Decimal | None]:
    """Devolve (novo valor, multiplicador ou None quando a ação soma/subtrai)."""
    hundred = Decimal("1") * 100
    if rule.action == "INCREASE_PERCENT":
        factor = Decimal("1") + rule.value / hundred
        return amount * factor, factor
    if rule.action == "DISCOUNT_PERCENT":
        factor = Decimal("1") - rule.value / hundred
        return amount * factor, factor
    if rule.action == "MULTIPLY":
        return amount * rule.value, rule.value
    if rule.action == "ADD_AMOUNT":
        return amount + rule.value, None
    if rule.action == "SUBTRACT_AMOUNT":
        return max(amount - rule.value, Decimal("0")), None
    raise ValueError(rule.action)


def field_catalog() -> dict[str, Any]:
    """Catálogo para a interface desenhar o construtor de regras sem o duplicar:
    se amanhã o backend ganhar um campo ou uma ação, o ecrã passa a mostrá-lo."""
    return {
        "fields": [
            {"key": key, "label": FIELD_LABELS[key], "kind": kind, "options": list(options) if options else None,
             "personOnly": key in PERSON_ONLY_FIELDS}
            for key, (_, kind, options) in FIELDS.items()
        ],
        "operators": [{"key": k, "label": OPERATOR_LABELS[k]} for k in OPERATORS],
        "scopes": [{"key": k, "label": SCOPE_LABELS[k]} for k in SCOPES],
        "actions": [
            {"key": k, "label": ACTION_LABELS[k], "group": "PRICING" if k in PRICING_ACTIONS else "UNDERWRITING",
             "needsValue": k in VALUE_ACTIONS, "unit": ACTION_UNITS.get(k)}
            for k in ACTIONS
        ],
    }


def describe(rule: CustomRule) -> str:
    """Frase legível, usada em rastos de cálculo e requisitos."""
    parts = []
    for c in rule.conditions:
        text = f"{FIELD_LABELS[c.field]} {OPERATOR_LABELS[c.operator]} {c.value}"
        if c.operator == "BETWEEN":
            text += f" e {c.value_to}"
        parts.append(text)
    return f"{rule.name}: quando " + " e ".join(parts)
