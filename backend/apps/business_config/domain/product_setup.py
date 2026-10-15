"""Configuração de tarifação por produto (grupos de opções, campos, valores e
fórmulas), editável pela interface — como os ecrãs «Grupo de opções»,
«Campos», «Valores» e «Fórmulas» de um produto.

Guarda-se como configuração de negócio com a chave
`product.pricing_setup:<id do produto>`, por isso tem versões, rascunho,
aprovação por outra pessoa, histórico, comparação e documentos anexos como
as restantes configurações.

Forma do valor:

    {
      "optionGroups": [
        {"code": "modalidade", "name": "Modalidade de Pagamento do Seguro",
         "listType": "RADIO", "required": true, "maxSelected": 1,
         "showInForm": true, "order": 1, "description": "",
         "options": [{"code": "anual", "label": "Anual"}, ...]}
      ],
      "fields": [
        {"code": "massa_salarial", "label": "Massa Salarial", "type": "NUMBER",
         "required": true, "min": "0", "max": null, "default": null,
         "unit": "AOA", "showInForm": true, "order": 2, "description": ""}
      ],
      "values": [                       # «Taxas e Valores», um por grupo
        {"group": "actividade", "type": "SIMPLE", "aggregate": "SUM",
         "unit": "PERCENT", "rows": [{"option": "comercio", "value": "0.02"}]}
      ],
      "formulas": [
        {"code": "premio_anual", "name": "Prémio anual",
         "expression": "actividade * massa_salarial * multiplicador",
         "flags": {"premium": true, "capital": false, "hidden": false,
                   "fractionation": false, "conversion": false},
         "frequency": null, "unit": "AOA", "minResult": null, "order": 1,
         "active": true, "description": "",
         "scope": {"categories": [], "plans": [], "policyTypes": []}}
      ]
    }

Tipos de valor (`values[].type`):

- `SIMPLE` (Simples): um valor por opção do grupo.
- `MULTIPLE` (Múltiplas opções): um valor por combinação de opções de vários
  grupos (`rows[].options = {grupo: opção}`).
- `FIXED` (Fixo): um valor único para o grupo (`value`).
- `AGE_INTERVAL` (Por intervalo de idade): `rows[] = {ageFrom, ageTo, value}`,
  avaliado para cada pessoa segura (opcionalmente só com `option` escolhida).
- `FIELD_VALUE` (Pelo valor do campo): `field` numérico e `rows[] = {from,
  to, value}` pelo valor desse campo.
- `OPTION_CONDITIONAL` (Condicional de opção): o valor da opção depende da
  opção escolhida noutro grupo (`conditionGroup`; `rows[] = {when, option,
  value}`).

Nomes que uma fórmula pode usar:

- o código de um grupo: o valor do grupo para as opções escolhidas (somado,
  ou `aggregate` = PRODUCT/MAX/MIN; o mesmo para várias pessoas);
- `<grupo>__<opção>`: 1 se a opção está escolhida, senão 0;
- o código de um campo numérico: o valor preenchido;
- o código de outra fórmula: o seu resultado (sem dependências circulares);
- `premio_tecnico` (prémio calculado pelo motor antes das fórmulas do
  produto) e `pessoas` (número de pessoas seguras).

Indicadores (`flags`):

- `premium`: o resultado passa a ser o prémio anual da cotação (no máximo
  uma fórmula de prémio por cotação);
- `capital`: o resultado é um capital (não mexe no prémio);
- `hidden`: calcula-se mas não se mostra ao cliente;
- `fractionation`: valor de cada prestação na frequência `frequency`
  (SEMESTRAL, TRIMESTRAL, MENSAL; ANUAL = uma prestação), usado na emissão;
- `conversion`: guardado e devolvido; a regra de conversão (moeda/unidade)
  não está definida no material do negócio e não altera o cálculo (lacuna
  documentada).

`minResult`: o resultado nunca fica abaixo deste valor. Resultados em AOA
são arredondados a 2 casas, meio-para-cima. As expressões são avaliadas pelo
avaliador seguro de `formula_engine` (sem `eval`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from apps.business_config.domain.errors import InvalidConfiguration, ProductSetupInputError
from apps.business_config.domain.formula_engine import FormulaError, evaluate_formula, parse_formula

KEY_PREFIX = "product.pricing_setup:"

LIST_TYPES = ("RADIO", "SELECT", "CHECKBOX", "TOGGLE", "AUTOCOMPLETE")
FIELD_TYPES = ("NUMBER", "INTEGER", "TEXT", "DATE", "BOOLEAN")
NUMERIC_FIELD_TYPES = ("NUMBER", "INTEGER")
VALUE_TYPES = ("SIMPLE", "MULTIPLE", "FIXED", "AGE_INTERVAL", "FIELD_VALUE", "OPTION_CONDITIONAL")
VALUE_TYPE_LABELS = {
    "SIMPLE": "Simples",
    "MULTIPLE": "Múltiplas opções",
    "FIXED": "Fixo",
    "AGE_INTERVAL": "Por intervalo de idade",
    "FIELD_VALUE": "Pelo valor do campo",
    "OPTION_CONDITIONAL": "Condicional de opção",
}
AGGREGATES = ("SUM", "PRODUCT", "MAX", "MIN")
UNITS = ("AOA", "PERCENT", "RATIO", "FACTOR", "COUNT", "OTHER")
MONETARY_UNITS = ("AOA",)
FREQUENCIES = ("ANUAL", "SEMESTRAL", "TRIMESTRAL", "MENSAL")
POLICY_TYPES = ("INDIVIDUAL", "GROUP")
FLAGS = ("premium", "capital", "hidden", "fractionation", "conversion")
SYSTEM_VARIABLES = {
    "premio_tecnico": "Prémio calculado pelo motor (antes das fórmulas do produto)",
    "pessoas": "Número de pessoas seguras",
}

MAX_GROUPS = 60
MAX_OPTIONS = 200
MAX_FIELDS = 100
MAX_ROWS = 2000
MAX_FORMULAS = 60
SAFETY_LIMIT = Decimal("1000000000000000")

_CODE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


def config_key(product_id: Any) -> str:
    return f"{KEY_PREFIX}{product_id}"


def is_product_setup_key(key: str) -> bool:
    return isinstance(key, str) and key.startswith(KEY_PREFIX)


def product_id_of(key: str) -> str:
    return key[len(KEY_PREFIX):]


# ------------------------------------------------------------------ parsing
def _err(path: str, message: str) -> InvalidConfiguration:
    return InvalidConfiguration(f"{path}: {message}")


def _code(raw: Any, path: str) -> str:
    if not isinstance(raw, str) or not _CODE.match(raw):
        raise _err(path, "código inválido (minúsculas, algarismos e _, a começar por letra, até 60 caracteres)")
    if "__" in raw:
        raise _err(path, "o código não pode ter «__» (reservado para <grupo>__<opção>)")
    return raw


def _text(raw: Any, path: str, *, required: bool = True, max_length: int = 300) -> str:
    if raw is None or raw == "":
        if required:
            raise _err(path, "obrigatório")
        return ""
    if not isinstance(raw, str) or len(raw) > max_length:
        raise _err(path, f"texto até {max_length} caracteres")
    return raw.strip()


def _decimal(raw: Any, path: str, *, required: bool = True) -> Decimal | None:
    if raw is None or raw == "":
        if required:
            raise _err(path, "valor obrigatório")
        return None
    if isinstance(raw, bool):
        raise _err(path, "tem de ser um número")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise _err(path, "tem de ser um número") from None
    if not value.is_finite() or abs(value) > SAFETY_LIMIT:
        raise _err(path, "número fora do intervalo permitido")
    return value


def _bool(raw: Any, path: str, default: bool) -> bool:
    if raw is None:
        return default
    if not isinstance(raw, bool):
        raise _err(path, "tem de ser verdadeiro ou falso")
    return raw


def _int(raw: Any, path: str, *, default: int | None = None, minimum: int = 0) -> int | None:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < minimum:
        raise _err(path, f"tem de ser um inteiro ≥ {minimum}")
    return raw


def _choice(raw: Any, path: str, choices: tuple[str, ...], default: str | None = None) -> str:
    if raw is None and default is not None:
        return default
    if raw not in choices:
        raise _err(path, f"tem de ser um de {list(choices)}")
    return raw


def _list(raw: Any, path: str, limit: int) -> list:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _err(path, "tem de ser uma lista")
    if len(raw) > limit:
        raise _err(path, f"no máximo {limit} elementos")
    return raw


def _obj(raw: Any, path: str) -> dict:
    if not isinstance(raw, dict):
        raise _err(path, "tem de ser um objeto")
    return raw


@dataclass(frozen=True)
class OptionGroup:
    code: str
    name: str
    list_type: str
    required: bool
    max_selected: int | None
    show_in_form: bool
    order: int
    description: str
    options: tuple[tuple[str, str], ...]  # (código, rótulo)

    @property
    def option_codes(self) -> tuple[str, ...]:
        return tuple(code for code, _ in self.options)


@dataclass(frozen=True)
class Field:
    code: str
    label: str
    type: str
    required: bool
    minimum: Decimal | None
    maximum: Decimal | None
    default: Any
    unit: str
    show_in_form: bool
    order: int
    description: str


@dataclass(frozen=True)
class ValueTable:
    group: str
    type: str
    aggregate: str
    unit: str
    value: Decimal | None
    field: str | None
    condition_group: str | None
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Formula:
    code: str
    name: str
    expression: str
    names: frozenset[str]
    flags: dict[str, bool]
    frequency: str | None
    unit: str
    min_result: Decimal | None
    order: int
    active: bool
    description: str
    scope: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class ProductSetup:
    groups: dict[str, OptionGroup]
    fields: dict[str, Field]
    values: dict[str, ValueTable]
    formulas: dict[str, Formula]
    evaluation_order: tuple[str, ...]

    def tokens(self) -> list[dict[str, Any]]:
        """O que o editor de fórmulas pode usar (separadores Grupos/Opções/Campos)."""
        out: list[dict[str, Any]] = []
        for group in sorted(self.groups.values(), key=lambda g: (g.order, g.code)):
            table = self.values.get(group.code)
            out.append({"kind": "GROUP", "token": group.code, "label": group.name,
                        "valueType": table.type if table else None,
                        "aggregate": table.aggregate if table else None})
            for code, label in group.options:
                out.append({"kind": "OPTION", "token": f"{group.code}__{code}", "label": f"{group.name}: {label}",
                            "group": group.code})
        for item in sorted(self.fields.values(), key=lambda f: (f.order, f.code)):
            if item.type in NUMERIC_FIELD_TYPES:
                out.append({"kind": "FIELD", "token": item.code, "label": item.label, "unit": item.unit})
        for formula in sorted(self.formulas.values(), key=lambda f: (f.order, f.code)):
            out.append({"kind": "FORMULA", "token": formula.code, "label": formula.name, "unit": formula.unit})
        for code, label in SYSTEM_VARIABLES.items():
            out.append({"kind": "SYSTEM", "token": code, "label": label})
        return out

    def form(self) -> dict[str, Any]:
        """Formulário da cotação (separador «Formulário»): grupos e campos visíveis por ordem."""
        items = [
            {"kind": "OPTION_GROUP", "order": g.order, "code": g.code, "label": g.name, "listType": g.list_type,
             "required": g.required, "maxSelected": g.max_selected, "description": g.description,
             "options": [{"code": c, "label": label} for c, label in g.options]}
            for g in self.groups.values() if g.show_in_form
        ] + [
            {"kind": "FIELD", "order": f.order, "code": f.code, "label": f.label, "type": f.type,
             "required": f.required, "min": _s(f.minimum), "max": _s(f.maximum), "default": f.default,
             "unit": f.unit, "description": f.description}
            for f in self.fields.values() if f.show_in_form
        ]
        return {"items": sorted(items, key=lambda i: (i["order"], i["code"]))}


def _s(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _parse_groups(rows: list) -> dict[str, OptionGroup]:
    groups: dict[str, OptionGroup] = {}
    for i, raw in enumerate(rows):
        path = f"optionGroups[{i}]"
        row = _obj(raw, path)
        code = _code(row.get("code"), f"{path}.code")
        if code in groups:
            raise _err(f"{path}.code", f"grupo «{code}» repetido")
        options = []
        seen: set[str] = set()
        for j, opt in enumerate(_list(row.get("options"), f"{path}.options", MAX_OPTIONS)):
            opt_path = f"{path}.options[{j}]"
            opt = _obj(opt, opt_path)
            opt_code = _code(opt.get("code"), f"{opt_path}.code")
            if opt_code in seen:
                raise _err(f"{opt_path}.code", f"opção «{opt_code}» repetida no grupo")
            seen.add(opt_code)
            options.append((opt_code, _text(opt.get("label"), f"{opt_path}.label")))
        if not options:
            raise _err(f"{path}.options", "o grupo precisa de pelo menos uma opção")
        list_type = _choice(row.get("listType"), f"{path}.listType", LIST_TYPES, "RADIO")
        max_selected = _int(row.get("maxSelected"), f"{path}.maxSelected", minimum=1)
        if list_type in ("RADIO", "SELECT", "TOGGLE", "AUTOCOMPLETE") and max_selected not in (None, 1):
            raise _err(f"{path}.maxSelected", f"uma lista {list_type} só aceita uma opção")
        groups[code] = OptionGroup(
            code=code, name=_text(row.get("name"), f"{path}.name"), list_type=list_type,
            required=_bool(row.get("required"), f"{path}.required", False),
            max_selected=1 if list_type != "CHECKBOX" else max_selected,
            show_in_form=_bool(row.get("showInForm"), f"{path}.showInForm", True),
            order=_int(row.get("order"), f"{path}.order", default=i + 1),
            description=_text(row.get("description"), f"{path}.description", required=False, max_length=1000),
            options=tuple(options),
        )
    return groups


def _parse_fields(rows: list, taken: set[str]) -> dict[str, Field]:
    fields: dict[str, Field] = {}
    for i, raw in enumerate(rows):
        path = f"fields[{i}]"
        row = _obj(raw, path)
        code = _code(row.get("code"), f"{path}.code")
        if code in fields or code in taken:
            raise _err(f"{path}.code", f"o código «{code}» já é usado por outro grupo/campo")
        ftype = _choice(row.get("type"), f"{path}.type", FIELD_TYPES, "NUMBER")
        minimum = _decimal(row.get("min"), f"{path}.min", required=False)
        maximum = _decimal(row.get("max"), f"{path}.max", required=False)
        if minimum is not None and maximum is not None and maximum < minimum:
            raise _err(f"{path}.max", "não pode ser menor do que o mínimo")
        default = row.get("default")
        if default not in (None, "") and ftype in NUMERIC_FIELD_TYPES:
            _decimal(default, f"{path}.default")
        fields[code] = Field(
            code=code, label=_text(row.get("label"), f"{path}.label"), type=ftype,
            required=_bool(row.get("required"), f"{path}.required", False), minimum=minimum, maximum=maximum,
            default=None if default == "" else default,
            unit=_text(row.get("unit"), f"{path}.unit", required=False, max_length=20),
            show_in_form=_bool(row.get("showInForm"), f"{path}.showInForm", True),
            order=_int(row.get("order"), f"{path}.order", default=100 + i),
            description=_text(row.get("description"), f"{path}.description", required=False, max_length=1000),
        )
    return fields


def _option_of(group: OptionGroup, raw: Any, path: str) -> str:
    if raw not in group.option_codes:
        raise _err(path, f"«{raw}» não é opção do grupo «{group.code}» (opções: {list(group.option_codes)})")
    return raw


def _parse_values(rows: list, groups: dict[str, OptionGroup], fields: dict[str, Field]) -> dict[str, ValueTable]:
    tables: dict[str, ValueTable] = {}
    for i, raw in enumerate(rows):
        path = f"values[{i}]"
        row = _obj(raw, path)
        group_code = row.get("group")
        if group_code not in groups:
            raise _err(f"{path}.group", f"grupo «{group_code}» não existe")
        if group_code in tables:
            raise _err(f"{path}.group", f"o grupo «{group_code}» já tem valores")
        group = groups[group_code]
        vtype = _choice(row.get("type"), f"{path}.type", VALUE_TYPES, "SIMPLE")
        items = _list(row.get("rows"), f"{path}.rows", MAX_ROWS)
        parsed: list[dict[str, Any]] = []
        value = None
        field = None
        condition_group = None
        if vtype == "FIXED":
            value = _decimal(row.get("value"), f"{path}.value")
        for j, item in enumerate(items):
            rp = f"{path}.rows[{j}]"
            item = _obj(item, rp)
            entry: dict[str, Any] = {"value": _decimal(item.get("value"), f"{rp}.value")}
            if vtype == "SIMPLE":
                entry["option"] = _option_of(group, item.get("option"), f"{rp}.option")
            elif vtype == "MULTIPLE":
                combo = _obj(item.get("options"), f"{rp}.options")
                if not combo:
                    raise _err(f"{rp}.options", "indique pelo menos uma opção")
                for g, opt in combo.items():
                    if g not in groups:
                        raise _err(f"{rp}.options", f"grupo «{g}» não existe")
                    _option_of(groups[g], opt, f"{rp}.options.{g}")
                entry["options"] = dict(combo)
            elif vtype == "AGE_INTERVAL":
                age_from = _int(item.get("ageFrom"), f"{rp}.ageFrom", default=0)
                age_to = _int(item.get("ageTo"), f"{rp}.ageTo", default=150)
                if age_to < age_from:
                    raise _err(f"{rp}.ageTo", "não pode ser menor do que ageFrom")
                entry.update(ageFrom=age_from, ageTo=age_to)
                if item.get("option") is not None:
                    entry["option"] = _option_of(group, item.get("option"), f"{rp}.option")
            elif vtype == "FIELD_VALUE":
                low = _decimal(item.get("from"), f"{rp}.from", required=False)
                high = _decimal(item.get("to"), f"{rp}.to", required=False)
                if low is not None and high is not None and high < low:
                    raise _err(f"{rp}.to", "não pode ser menor do que from")
                entry.update({"from": low, "to": high})
                if item.get("option") is not None:
                    entry["option"] = _option_of(group, item.get("option"), f"{rp}.option")
            elif vtype == "OPTION_CONDITIONAL":
                entry["option"] = _option_of(group, item.get("option"), f"{rp}.option")
                entry["when"] = item.get("when")  # validado com conditionGroup abaixo
            parsed.append(entry)
        if vtype == "FIELD_VALUE":
            field = row.get("field")
            if field not in fields or fields[field].type not in NUMERIC_FIELD_TYPES:
                raise _err(f"{path}.field", f"«{field}» não é um campo numérico")
        if vtype == "OPTION_CONDITIONAL":
            condition_group = row.get("conditionGroup")
            if condition_group not in groups or condition_group == group_code:
                raise _err(f"{path}.conditionGroup", f"«{condition_group}» tem de ser outro grupo existente")
            for j, entry in enumerate(parsed):
                _option_of(groups[condition_group], entry["when"], f"{path}.rows[{j}].when")
        if vtype != "FIXED" and not parsed:
            raise _err(f"{path}.rows", "indique pelo menos uma linha de valores")
        tables[group_code] = ValueTable(
            group=group_code, type=vtype, aggregate=_choice(row.get("aggregate"), f"{path}.aggregate", AGGREGATES, "SUM"),
            unit=_choice(row.get("unit"), f"{path}.unit", UNITS, "FACTOR"), value=value, field=field,
            condition_group=condition_group, rows=tuple(parsed),
        )
    return tables


def _parse_scope(raw: Any, path: str) -> dict[str, tuple[str, ...]]:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise _err(path, "tem de ser um objeto")
    scope: dict[str, tuple[str, ...]] = {}
    for key in ("categories", "plans", "policyTypes"):
        items = _list(raw.get(key), f"{path}.{key}", 200)
        if not all(isinstance(x, str) and x for x in items):
            raise _err(f"{path}.{key}", "lista de textos")
        if key == "policyTypes":
            for x in items:
                _choice(x, f"{path}.policyTypes", POLICY_TYPES)
        scope[key] = tuple(items)
    return scope


def _parse_formulas(rows: list, names: set[str]) -> dict[str, Formula]:
    formulas: dict[str, Formula] = {}
    for i, raw in enumerate(rows):
        path = f"formulas[{i}]"
        row = _obj(raw, path)
        code = _code(row.get("code"), f"{path}.code")
        if code in formulas or code in names or code in SYSTEM_VARIABLES:
            raise _err(f"{path}.code", f"o código «{code}» já é usado")
        expression = row.get("expression")
        try:
            _, referenced = parse_formula(expression)
        except FormulaError as exc:
            raise _err(f"{path}.expression", str(exc)) from None
        flags_raw = row.get("flags") or {}
        if not isinstance(flags_raw, dict) or set(flags_raw) - set(FLAGS):
            raise _err(f"{path}.flags", f"indicadores permitidos: {list(FLAGS)}")
        flags = {name: _bool(flags_raw.get(name), f"{path}.flags.{name}", False) for name in FLAGS}
        if flags["premium"] and (flags["capital"] or flags["fractionation"]):
            raise _err(f"{path}.flags", "uma fórmula de prémio não pode ser também capital ou fracionamento")
        frequency = row.get("frequency")
        if flags["fractionation"]:
            frequency = _choice(frequency, f"{path}.frequency", FREQUENCIES)
        elif frequency is not None:
            raise _err(f"{path}.frequency", "só se indica a frequência numa fórmula de fracionamento")
        formulas[code] = Formula(
            code=code, name=_text(row.get("name"), f"{path}.name"), expression=expression.strip(),
            names=frozenset(referenced), flags=flags, frequency=frequency,
            unit=_choice(row.get("unit"), f"{path}.unit", UNITS, "AOA"),
            min_result=_decimal(row.get("minResult"), f"{path}.minResult", required=False),
            order=_int(row.get("order"), f"{path}.order", default=i + 1),
            active=_bool(row.get("active"), f"{path}.active", True),
            description=_text(row.get("description"), f"{path}.description", required=False, max_length=1000),
            scope=_parse_scope(row.get("scope"), f"{path}.scope"),
        )
    return formulas


def _resolve_order(formulas: dict[str, Formula], allowed: set[str]) -> tuple[str, ...]:
    for formula in formulas.values():
        unknown = sorted(formula.names - allowed - set(formulas))
        if unknown:
            raise InvalidConfiguration(
                f"Fórmula «{formula.code}»: nomes desconhecidos {unknown} (use grupos, <grupo>__<opção>, campos "
                f"numéricos, outras fórmulas ou {sorted(SYSTEM_VARIABLES)})"
            )
    ordered: list[str] = []
    state: dict[str, str] = {}

    def visit(code: str, chain: list[str]) -> None:
        if state.get(code) == "done":
            return
        if state.get(code) == "visiting":
            raise InvalidConfiguration(f"Dependência circular entre fórmulas: {' → '.join(chain + [code])}")
        state[code] = "visiting"
        for dep in sorted(formulas[code].names & set(formulas), key=lambda c: (formulas[c].order, c)):
            visit(dep, chain + [code])
        state[code] = "done"
        ordered.append(code)

    for code in sorted(formulas, key=lambda c: (formulas[c].order, c)):
        visit(code, [])
    return tuple(ordered)


def parse_product_setup(value: Any) -> ProductSetup:
    value = _obj(value, "configuração")
    unknown = set(value) - {"optionGroups", "fields", "values", "formulas"}
    if unknown:
        raise InvalidConfiguration(f"Secções desconhecidas: {sorted(unknown)} (permitidas: optionGroups, fields, values, formulas)")
    groups = _parse_groups(_list(value.get("optionGroups"), "optionGroups", MAX_GROUPS))
    fields = _parse_fields(_list(value.get("fields"), "fields", MAX_FIELDS), set(groups))
    values = _parse_values(_list(value.get("values"), "values", MAX_GROUPS), groups, fields)
    option_tokens = {f"{g.code}__{o}" for g in groups.values() for o in g.option_codes}
    numeric_fields = {c for c, f in fields.items() if f.type in NUMERIC_FIELD_TYPES}
    clashes = sorted(set(SYSTEM_VARIABLES) & (set(groups) | set(fields)))
    if clashes:
        raise InvalidConfiguration(f"Códigos reservados pelo sistema: {clashes}")
    names = set(groups) | set(fields) | option_tokens
    formulas = _parse_formulas(_list(value.get("formulas"), "formulas", MAX_FORMULAS), names)
    allowed = set(values) | option_tokens | numeric_fields | set(SYSTEM_VARIABLES)
    for formula in formulas.values():
        without_values = sorted(formula.names & (set(groups) - set(values)))
        if without_values:
            raise InvalidConfiguration(f"Fórmula «{formula.code}»: os grupos {without_values} ainda não têm valores definidos")
        text_fields = sorted(formula.names & (set(fields) - numeric_fields))
        if text_fields:
            raise InvalidConfiguration(f"Fórmula «{formula.code}»: os campos {text_fields} não são numéricos")
    order = _resolve_order(formulas, allowed)
    return ProductSetup(groups=groups, fields=fields, values=values, formulas=formulas, evaluation_order=order)


def validate_product_setup(value: Any) -> None:
    parse_product_setup(value)


# --------------------------------------------------------------- avaliação
def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalise_inputs(setup: ProductSetup, options: Any, fields: Any, *, require: bool) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    """Valida as escolhas da cotação (`productOptions` = {grupo: [opções]},
    `productFields` = {campo: valor}). Com `require`, exige os obrigatórios."""
    options = options or {}
    fields = fields or {}
    if not isinstance(options, dict):
        raise ProductSetupInputError("productOptions tem de ser um objeto {grupo: [opções]}")
    if not isinstance(fields, dict):
        raise ProductSetupInputError("productFields tem de ser um objeto {campo: valor}")
    chosen: dict[str, tuple[str, ...]] = {}
    for code, raw in options.items():
        group = setup.groups.get(code)
        if group is None:
            raise ProductSetupInputError(f"productOptions: o grupo «{code}» não existe neste produto")
        picked = [raw] if isinstance(raw, str) else raw
        if not isinstance(picked, list) or not all(isinstance(x, str) for x in picked):
            raise ProductSetupInputError(f"productOptions.{code}: lista de códigos de opção")
        unknown = [x for x in picked if x not in group.option_codes]
        if unknown:
            raise ProductSetupInputError(f"productOptions.{code}: {unknown} não são opções de «{group.name}»")
        picked = list(dict.fromkeys(picked))
        limit = group.max_selected or len(group.option_codes)
        if len(picked) > limit:
            raise ProductSetupInputError(f"productOptions.{code}: no máximo {limit} opção(ões)")
        if picked:
            chosen[code] = tuple(picked)
    values: dict[str, Any] = {}
    for code, raw in fields.items():
        item = setup.fields.get(code)
        if item is None:
            raise ProductSetupInputError(f"productFields: o campo «{code}» não existe neste produto")
        if raw is None or raw == "":
            continue
        if item.type in NUMERIC_FIELD_TYPES:
            try:
                number = Decimal(str(raw))
            except (InvalidOperation, ValueError):
                raise ProductSetupInputError(f"productFields.{code}: «{item.label}» tem de ser um número") from None
            if isinstance(raw, bool) or not number.is_finite():
                raise ProductSetupInputError(f"productFields.{code}: «{item.label}» tem de ser um número")
            if item.type == "INTEGER" and number != number.to_integral_value():
                raise ProductSetupInputError(f"productFields.{code}: «{item.label}» tem de ser um número inteiro")
            if item.minimum is not None and number < item.minimum:
                raise ProductSetupInputError(f"productFields.{code}: «{item.label}» não pode ser menor do que {item.minimum}")
            if item.maximum is not None and number > item.maximum:
                raise ProductSetupInputError(f"productFields.{code}: «{item.label}» não pode ser maior do que {item.maximum}")
            values[code] = str(number)
        elif item.type == "BOOLEAN":
            if not isinstance(raw, bool):
                raise ProductSetupInputError(f"productFields.{code}: «{item.label}» tem de ser verdadeiro ou falso")
            values[code] = raw
        else:
            if not isinstance(raw, str) or len(raw) > 500:
                raise ProductSetupInputError(f"productFields.{code}: «{item.label}» tem de ser texto (até 500 caracteres)")
            values[code] = raw
    if require:
        missing = [g.name for g in setup.groups.values() if g.required and g.code not in chosen]
        missing += [f.label for f in setup.fields.values() if f.required and f.code not in values and f.default in (None, "")]
        if missing:
            raise ProductSetupInputError(f"Falta preencher: {', '.join(missing)}")
    return chosen, values


def _aggregate(values: list[Decimal], how: str) -> Decimal:
    if not values:
        return Decimal("0")
    if how == "PRODUCT":
        out = Decimal("1")
        for v in values:
            out *= v
        return out
    if how == "MAX":
        return max(values)
    if how == "MIN":
        return min(values)
    return sum(values, Decimal("0"))


def _field_number(setup: ProductSetup, fields: dict[str, Any], code: str) -> Decimal | None:
    raw = fields.get(code, setup.fields[code].default)
    return None if raw in (None, "") else Decimal(str(raw))


def _group_value(setup: ProductSetup, table: ValueTable, chosen: dict[str, tuple[str, ...]], fields: dict[str, Any], ages: list[int]) -> Decimal:
    group = setup.groups[table.group]
    picked = chosen.get(table.group, ())
    if table.type == "FIXED":
        return table.value
    if table.type == "MULTIPLE":
        hits = [r["value"] for r in table.rows
                if all(opt in chosen.get(g, ()) for g, opt in r["options"].items())]
        if not hits and picked:
            raise ProductSetupInputError(f"«{group.name}»: não há valor para esta combinação de opções")
        return _aggregate(hits, table.aggregate)
    if table.type == "AGE_INTERVAL":
        hits = []
        for age in ages:
            row = next((r for r in table.rows
                        if r["ageFrom"] <= age <= r["ageTo"] and ("option" not in r or r["option"] in picked)), None)
            if row is None:
                raise ProductSetupInputError(f"«{group.name}»: não há valor para a idade {age}")
            hits.append(row["value"])
        return _aggregate(hits, table.aggregate)
    if table.type == "FIELD_VALUE":
        number = _field_number(setup, fields, table.field)
        if number is None:
            raise ProductSetupInputError(f"«{group.name}»: preencha o campo «{setup.fields[table.field].label}»")
        row = next((r for r in table.rows
                    if (r["from"] is None or number >= r["from"]) and (r["to"] is None or number <= r["to"])
                    and ("option" not in r or r["option"] in picked)), None)
        if row is None:
            raise ProductSetupInputError(f"«{group.name}»: não há valor para {setup.fields[table.field].label} = {number}")
        return row["value"]
    if not picked:
        if group.required:
            raise ProductSetupInputError(f"Escolha uma opção em «{group.name}»")
        return Decimal("0")
    if table.type == "SIMPLE":
        by_option = {r["option"]: r["value"] for r in table.rows}
        missing = [o for o in picked if o not in by_option]
        if missing:
            raise ProductSetupInputError(f"«{group.name}»: as opções {missing} não têm valor definido")
        return _aggregate([by_option[o] for o in picked], table.aggregate)
    # OPTION_CONDITIONAL
    condition = chosen.get(table.condition_group, ())
    hits = []
    for option in picked:
        row = next((r for r in table.rows if r["option"] == option and r["when"] in condition), None)
        if row is None:
            other = setup.groups[table.condition_group].name
            raise ProductSetupInputError(f"«{group.name}»: não há valor para «{option}» com a escolha feita em «{other}»")
        hits.append(row["value"])
    return _aggregate(hits, table.aggregate)


def applies_to(formula: Formula, *, category: str | None, plan_code: str | None, policy_type: str | None) -> bool:
    scope = formula.scope
    return (
        (not scope["categories"] or category in scope["categories"])
        and (not scope["plans"] or plan_code in scope["plans"])
        and (not scope["policyTypes"] or policy_type in scope["policyTypes"])
    )


def evaluate_product_setup(
    setup: ProductSetup,
    *,
    options: Any = None,
    fields: Any = None,
    ages: list[int] | None = None,
    technical_premium: Decimal | str | None = None,
    members_count: int | None = None,
    category: str | None = None,
    plan_code: str | None = None,
    policy_type: str | None = None,
    require: bool = True,
    extra_expression: str | None = None,
) -> dict[str, Any]:
    """Calcula as fórmulas ativas que se aplicam (âmbito) pela ordem das
    dependências. Devolve os resultados, o valor de cada grupo usado e, se
    houver, o prémio anual e as prestações por frequência."""
    chosen, field_values = normalise_inputs(setup, options, fields, require=require)
    ages = [int(a) for a in (ages or [])]
    variables: dict[str, Decimal] = {
        "premio_tecnico": Decimal(str(technical_premium)) if technical_premium not in (None, "") else Decimal("0"),
        "pessoas": Decimal(members_count if members_count is not None else len(ages)),
    }
    for group in setup.groups.values():
        for option in group.option_codes:
            variables[f"{group.code}__{option}"] = Decimal("1") if option in chosen.get(group.code, ()) else Decimal("0")
    for code, item in setup.fields.items():
        if item.type in NUMERIC_FIELD_TYPES:
            number = _field_number(setup, field_values, code)
            if number is not None:
                variables[code] = number

    active = {
        code for code, f in setup.formulas.items()
        if f.active and applies_to(f, category=category, plan_code=plan_code, policy_type=policy_type)
    }
    # Uma fórmula ativa precisa das fórmulas de que depende, mesmo fora do âmbito.
    needed: set[str] = set()

    def need(code: str) -> None:
        if code in needed:
            return
        needed.add(code)
        for dep in setup.formulas[code].names & set(setup.formulas):
            need(dep)

    for code in active:
        need(code)
    extra_names: set[str] = set()
    if extra_expression is not None:
        try:
            _, extra_names = parse_formula(extra_expression)
        except FormulaError as exc:
            raise ProductSetupInputError(f"Expressão: {exc}") from None
        for dep in extra_names & set(setup.formulas):
            need(dep)

    group_values: dict[str, str] = {}

    def resolve(names: frozenset[str] | set[str]) -> None:
        for name in names:
            if name in setup.values and name not in variables:
                variables[name] = _group_value(setup, setup.values[name], chosen, field_values, ages)
                group_values[name] = str(variables[name])
            elif name in setup.fields and name not in variables:
                raise ProductSetupInputError(f"Preencha o campo «{setup.fields[name].label}»")

    results: list[dict[str, Any]] = []
    for code in setup.evaluation_order:
        if code not in needed:
            continue
        formula = setup.formulas[code]
        resolve(formula.names)
        try:
            raw = Decimal(str(evaluate_formula(formula.expression, variables)))
        except FormulaError as exc:
            raise ProductSetupInputError(f"Fórmula «{formula.name}»: {exc}") from None
        value = raw
        if formula.min_result is not None and value < formula.min_result:
            value = formula.min_result
        if formula.unit in MONETARY_UNITS:
            value = _round2(value)
        if abs(value) > SAFETY_LIMIT:
            raise ProductSetupInputError(f"Fórmula «{formula.name}»: resultado fora do intervalo permitido")
        variables[code] = value
        results.append({
            "code": code, "name": formula.name, "expression": formula.expression, "value": str(value),
            "rawValue": str(raw), "unit": formula.unit, "flags": dict(formula.flags), "frequency": formula.frequency,
            "minResultApplied": value != raw and formula.min_result is not None and raw < formula.min_result,
            "applies": code in active,
        })

    applied = [r for r in results if r["applies"]]
    premium = [r for r in applied if r["flags"]["premium"]]
    if len(premium) > 1:
        raise ProductSetupInputError(
            f"Mais de uma fórmula de prémio se aplica a esta cotação: {[r['code'] for r in premium]} (ajuste o âmbito)"
        )
    installments: dict[str, str] = {}
    for r in applied:
        if r["flags"]["fractionation"]:
            if r["frequency"] in installments:
                raise ProductSetupInputError(f"Mais de uma fórmula de fracionamento {r['frequency']} se aplica")
            installments[r["frequency"]] = r["value"]
    out: dict[str, Any] = {
        "results": results,
        "groupValues": group_values,
        "premium": premium[0]["value"] if premium else None,
        "premiumFormula": premium[0]["code"] if premium else None,
        "installments": installments,
        "selection": {"productOptions": {k: list(v) for k, v in chosen.items()}, "productFields": field_values},
    }
    if extra_expression is not None:
        resolve(extra_names)
        unknown = sorted(extra_names - set(variables))
        if unknown:
            raise ProductSetupInputError(f"Expressão: nomes desconhecidos {unknown}")
        try:
            out["expressionValue"] = str(Decimal(str(evaluate_formula(extra_expression, variables))))
        except FormulaError as exc:
            raise ProductSetupInputError(f"Expressão: {exc}") from None
    return out


def catalog() -> dict[str, Any]:
    return {
        "listTypes": list(LIST_TYPES),
        "fieldTypes": list(FIELD_TYPES),
        "valueTypes": [{"code": c, "label": VALUE_TYPE_LABELS[c]} for c in VALUE_TYPES],
        "aggregates": list(AGGREGATES),
        "units": list(UNITS),
        "frequencies": list(FREQUENCIES),
        "policyTypes": list(POLICY_TYPES),
        "flags": [
            {"code": "premium", "label": "Prémio", "help": "O resultado é o prémio anual da cotação."},
            {"code": "capital", "label": "Capital", "help": "O resultado é um capital (não altera o prémio)."},
            {"code": "hidden", "label": "Ocultar", "help": "Calcula-se, mas não se mostra ao cliente."},
            {"code": "fractionation", "label": "Fracionamento", "help": "Valor de cada prestação na frequência indicada."},
            {"code": "conversion", "label": "Conversão", "help": "Guardado; a regra de conversão ainda não está definida e não altera o cálculo."},
        ],
        "systemVariables": [{"token": k, "label": v} for k, v in SYSTEM_VARIABLES.items()],
        "operators": ["+", "-", "*", "/", "(", ")"],
        "functions": ["min", "max", "abs", "round"],
    }
