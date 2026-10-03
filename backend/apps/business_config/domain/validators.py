"""Validação estrutural de uma configuração antes de ser gravada em DRAFT.

Dirigida pelo esquema do formulário (`form_schemas`): tipos, obrigatórios,
opções fechadas e coerência entre campos. Valida a forma, não os valores
comerciais (esses são do negócio).
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.form_schemas import get_form_schema
from apps.business_config.domain.shape import flatten

# Campos cujas opções vêm de dados do sistema (planos, coberturas, países):
# o esquema sugere valores mas não os impõe.
_OPEN_OPTIONS = {"plan", "coverage", "included_in_plans", "applies_to", "countries"}
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _decimal(raw: Any, path: str, *, minimum: Decimal | None = Decimal("0")) -> Decimal:
    if isinstance(raw, bool):
        raise InvalidConfiguration(f"{path}: número inválido")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise InvalidConfiguration(f"{path}: número inválido") from None
    if not value.is_finite() or (minimum is not None and value < minimum):
        raise InvalidConfiguration(f"{path}: deve ser um número ≥ {minimum}")
    return value


def _check_field(field: dict[str, Any], raw: Any, path: str) -> None:
    kind, name = field["type"], field["name"]
    if raw is None or raw == "":
        if field.get("required"):
            raise InvalidConfiguration(f"{path}: campo obrigatório")
        return
    if kind in ("text", "textarea"):
        if not isinstance(raw, str):
            raise InvalidConfiguration(f"{path}: deve ser texto")
    elif kind == "boolean":
        if not isinstance(raw, bool):
            raise InvalidConfiguration(f"{path}: deve ser verdadeiro/falso")
    elif kind == "integer":
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise InvalidConfiguration(f"{path}: deve ser um inteiro ≥ 0")
    elif kind in ("decimal", "money"):
        _decimal(raw, path)
    elif kind == "select":
        options = field.get("options")
        if options and name not in _OPEN_OPTIONS and raw not in options:
            raise InvalidConfiguration(f"{path}: valor '{raw}' inválido (permitidos: {options})")
    elif kind == "multiselect":
        if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
            raise InvalidConfiguration(f"{path}: deve ser uma lista de textos")
        options = field.get("options")
        if options and name not in _OPEN_OPTIONS and not set(raw) <= set(options):
            raise InvalidConfiguration(f"{path}: valores inválidos {sorted(set(raw) - set(options))}")


def _check_object(fields: list[dict[str, Any]], row: Any, path: str) -> None:
    if not isinstance(row, dict):
        raise InvalidConfiguration(f"{path}: deve ser um objeto")
    known = {f["name"] for f in fields}
    unknown = set(row) - known
    if unknown:
        raise InvalidConfiguration(f"{path}: campos desconhecidos {sorted(unknown)}")
    for field in fields:
        _check_field(field, row.get(field["name"]), f"{path}.{field['name']}")


def validate_structure(key: str, value: dict[str, Any]) -> None:
    schema = get_form_schema(key)
    sections = schema["sections"]
    if len(sections) == 1 and sections[0]["fields"][0]["type"] == "json":
        return  # chave sem esquema próprio: aceita um objeto livre
    flat_fields = {f["name"]: f for s in sections if not s.get("repeatable") for f in s["fields"]}
    allowed = {s["key"] for s in sections} | set(flat_fields)
    unknown = set(value) - allowed
    if unknown:
        raise InvalidConfiguration(f"Secções desconhecidas: {sorted(unknown)} (permitidas: {sorted(allowed)})")
    for name, field in flat_fields.items():
        if name in value:
            _check_field(field, value[name], name)
    for section in sections:
        data = value.get(section["key"])
        if data is None:
            continue
        if section.get("repeatable"):
            if not isinstance(data, list):
                raise InvalidConfiguration(f"{section['key']}: deve ser uma lista")
            for index, row in enumerate(data):
                _check_object(section["fields"], row, f"{section['key']}[{index}]")
        else:
            _check_object(section["fields"], data, section["key"])
    _check_rules(key, value)


def _check_rules(key: str, value: dict[str, Any]) -> None:
    value = flatten(key, value)
    if key == "proposal.branding":
        color = value.get("primary_color")
        if color and not _COLOR.match(color):
            raise InvalidConfiguration("branding.primary_color: use o formato #RRGGBB")
    for row in value.get("premiums") or []:
        low, high = row.get("age_from"), row.get("age_to")
        if high is not None and low is not None and high < low:
            raise InvalidConfiguration(f"premiums: age_to ({high}) < age_from ({low})")
    for row in value.get("items") or []:
        if key == "product.age_limits" and row.get("renewal_max_age") is not None and row.get("entry_max_age") is not None:
            if row["renewal_max_age"] < row["entry_max_age"]:
                raise InvalidConfiguration("age_limits: a idade máxima de renovação não pode ser inferior à de entrada")
    if key == "pricing.factors":
        for row in value.get("factors") or []:
            if _decimal(row.get("factor"), "factors.factor") == 0:
                raise InvalidConfiguration("factors.factor: um multiplicador 0 anularia o prémio")


def validate_for_publication(key: str, value: dict[str, Any]) -> None:
    """Regras mais fortes, verificadas ao submeter para aprovação."""
    if key == "pricing.reference_premiums":
        value = flatten(key, value)
        if not value.get("currency_code"):
            raise InvalidConfiguration("pricing.reference_premiums: a moeda (currency_code) é obrigatória")
        if not (value.get("premiums") or []):
            raise InvalidConfiguration("pricing.reference_premiums: defina pelo menos uma tarifa")
