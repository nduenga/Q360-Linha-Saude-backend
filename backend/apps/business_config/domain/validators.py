"""Validação estrutural de uma configuração antes de ser gravada em DRAFT.

Dirigida pelo esquema do formulário (`form_schemas`): tipos, obrigatórios,
opções fechadas e coerência entre campos. Valida a forma, não os valores
comerciais (esses são do negócio).
"""
from __future__ import annotations

import re
import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.domain.actuarial_model import CONFIG_KEY as ACTUARIAL_KEY, validate_actuarial_model
from apps.business_config.domain.custom_rules import validate_rules
from apps.business_config.domain.formulas import CONFIG_KEY as FORMULAS_KEY, validate_formulas
from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.form_schemas import get_form_schema
from apps.business_config.domain.shape import flatten

# Campos cujas opções vêm de dados do sistema (planos, coberturas, países):
# o esquema sugere valores mas não os impõe.
_OPEN_OPTIONS = {"plan", "coverage", "included_in_plans", "applies_to", "countries", "products"}
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
    if key == FORMULAS_KEY:
        # Sintaxe, variáveis declaradas, dependências e ciclos: uma fórmula
        # inválida nunca chega a ser guardada, muito menos publicada.
        validate_formulas(value)
        return
    if key == ACTUARIAL_KEY:
        # Modelo editável pela interface/importado do Excel: tabelas e taxas
        # inválidas são recusadas ao gravar, nunca no cálculo.
        validate_actuarial_model(value)
        return
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


def _unique_per_plan(key: str, rows: list, identity) -> None:
    """Uma só linha por plano (e por cobertura, quando a linha a tem): a linha
    sem plano vale para todos e a do plano prevalece sobre ela."""
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        marker = (str(row.get("plan") or "").strip().casefold(), identity(row))
        if marker in seen:
            plan = row.get("plan") or "todos os planos"
            raise InvalidConfiguration(f"{key}: items[{index}] repete a linha de «{plan}»")
        seen.add(marker)


def _check_rules(key: str, value: dict[str, Any]) -> None:
    value = flatten(key, value)
    if key == "proposal.branding":
        color = value.get("primary_color")
        if color and not _COLOR.match(color):
            raise InvalidConfiguration("branding.primary_color: use o formato #RRGGBB")
    for row in value.get("premiums") or []:
        low, high = row.get("age_from"), row.get("age_to")
        if high is not None and low is not None and high < low:
            raise InvalidConfiguration(f"premiums: age_to ({high}) é inferior a age_from ({low})")
    for row in value.get("items") or []:
        if key == "product.age_limits" and row.get("renewal_max_age") is not None and row.get("entry_max_age") is not None:
            if row["renewal_max_age"] < row["entry_max_age"]:
                raise InvalidConfiguration("age_limits: a idade máxima de renovação não pode ser inferior à de entrada")
        if key == "product.age_limits" and row.get("entry_min_age") is not None and row.get("entry_max_age") is not None:
            if row["entry_max_age"] < row["entry_min_age"]:
                raise InvalidConfiguration("age_limits: a idade máxima de entrada não pode ser inferior à mínima")
    if key in ("product.age_limits", "product.minimum_premium"):
        _unique_per_plan(key, value.get("items") or [], lambda row: "")
    if key == "product.waiting_periods":
        _unique_per_plan(key, value.get("items") or [], lambda row: str(row.get("coverage") or "").strip().casefold())
    if key == "product.minimum_premium":
        for index, row in enumerate(value.get("items") or []):
            if row.get("annual_minimum") in (None, "") and row.get("per_person_minimum") in (None, ""):
                raise InvalidConfiguration(
                    f"items[{index}]: indique o prémio mínimo da apólice, o prémio mínimo por pessoa ou os dois")
    if key == "rules.custom":
        validate_rules(value)
    if key == "policy.endorsements":
        if value.get("minimum_premium") not in (None, "") and _decimal(value["minimum_premium"], "endorsements.minimum_premium") < 0:
            raise InvalidConfiguration("endorsements.minimum_premium: não pode ser negativo")
        if value.get("acceptance_days") == 0:
            raise InvalidConfiguration("endorsements.acceptance_days: indique pelo menos 1 dia")
    if key == "pricing.fractionation":
        frequencies = [row.get("frequency") for row in value.get("installments") or []]
        if len(frequencies) != len(set(frequencies)):
            raise InvalidConfiguration("installments: cada periodicidade só pode aparecer uma vez")
        for row in value.get("installments") or []:
            if _decimal(row.get("loading"), "installments.loading") >= 1:
                raise InvalidConfiguration("installments.loading: use uma fração inferior a 1 (ex.: 0.04 = 4 %)")
    if key == "pricing.factors":
        for row in value.get("factors") or []:
            if _decimal(row.get("factor"), "factors.factor") == 0:
                raise InvalidConfiguration("factors.factor: um multiplicador 0 anularia o prémio")
    if key == "quote.discount_approval":
        threshold = _decimal(value.get("approval_threshold_percent"), "approval_threshold_percent")
        if threshold > 100:
            raise InvalidConfiguration("approval_threshold_percent: deve ser no máximo 100 (a partir desse valor, a aprovação é obrigatória)")
    if key == "service.sla":
        priorities = [row.get("priority") for row in value.get("targets") or []]
        if len(priorities) != len(set(priorities)):
            raise InvalidConfiguration("targets: cada prioridade só pode ter uma meta")
        request_types = [row.get("request_type") for row in value.get("request_priorities") or []]
        if len(request_types) != len(set(request_types)):
            raise InvalidConfiguration("request_priorities: cada tipo de pedido só pode ter uma prioridade")
        for row in value.get("targets") or []:
            response, resolution = row.get("first_response_minutes"), row.get("resolution_minutes")
            if response is not None and resolution is not None and resolution < response:
                raise InvalidConfiguration("targets.resolution_minutes não pode ser inferior a first_response_minutes")
        if any(row.get("business_hours_only") for row in value.get("targets") or []):
            try:
                ZoneInfo(value.get("time_zone", ""))
            except ZoneInfoNotFoundError:
                raise InvalidConfiguration("calendar.time_zone tem de ser um fuso horário IANA válido") from None
            days = value.get("business_days") or []
            if not days:
                raise InvalidConfiguration("calendar.business_days: indique pelo menos um dia útil")
            try:
                opening = datetime.time.fromisoformat(value.get("business_start", ""))
                closing = datetime.time.fromisoformat(value.get("business_end", ""))
            except ValueError:
                raise InvalidConfiguration("calendar.business_start e business_end têm de usar HH:MM") from None
            if closing <= opening:
                raise InvalidConfiguration("calendar.business_end tem de ser posterior a business_start no mesmo dia")
            raw_holidays = value.get("holidays") or ""
            for holiday in filter(None, (line.strip() for line in raw_holidays.splitlines())):
                try:
                    datetime.date.fromisoformat(holiday)
                except ValueError:
                    raise InvalidConfiguration(f"calendar.holidays contém uma data inválida: {holiday}") from None
    if key == "service.satisfaction":
        if value.get("maximum_score", 0) <= value.get("minimum_score", 0):
            raise InvalidConfiguration("maximum_score deve ser superior a minimum_score")
    if key == "pricing.experience_rating":
        minimum, maximum = value.get("minimum_factor"), value.get("maximum_factor")
        if minimum is not None and _decimal(minimum, "minimum_factor") <= 0:
            raise InvalidConfiguration("minimum_factor deve ser superior a zero")
        if minimum is not None and maximum is not None and _decimal(maximum, "maximum_factor") < _decimal(minimum, "minimum_factor"):
            raise InvalidConfiguration("maximum_factor não pode ser inferior a minimum_factor")
        if value.get("target_value") is not None and _decimal(value["target_value"], "target_value") <= 0:
            raise InvalidConfiguration("target_value deve ser superior a zero")
        weight = value.get("weight_percent")
        if weight is not None and _decimal(weight, "weight_percent") > 100:
            raise InvalidConfiguration("weight_percent deve ser no máximo 100")
    if key == "quote.scenario_comparison":
        dimensions = value.get("radar_dimensions") or []
        if len(dimensions) < 3:
            raise InvalidConfiguration("radar_dimensions: selecione pelo menos três dimensões para o radar")
        expense = _decimal(value.get("expense_ratio_percent", 0), "expense_ratio_percent")
        commission = _decimal(value.get("commission_percent", 0), "commission_percent")
        if expense > 100 or commission > 100 or expense + commission > 100:
            raise InvalidConfiguration("expense_ratio_percent + commission_percent não pode exceder 100")
    if key == "claims.projections":
        horizon = value.get("horizon_months")
        if horizon is not None and horizon > 120:
            raise InvalidConfiguration("horizon_months: o horizonte máximo é 120 meses")


def validate_for_publication(key: str, value: dict[str, Any]) -> None:
    """Regras mais fortes, verificadas ao submeter para aprovação."""
    if key == "service.sla":
        targets = value.get("targets") or []
        if not targets:
            raise InvalidConfiguration("service.sla: defina pelo menos uma meta de atendimento")
        if not any(row.get("priority") == "NORMAL" for row in targets):
            raise InvalidConfiguration("service.sla: defina uma meta para a prioridade NORMAL, usada quando não há classificação específica")
    if key == "pricing.reference_premiums":
        value = flatten(key, value)
        if not value.get("currency_code"):
            raise InvalidConfiguration("pricing.reference_premiums: a moeda (currency_code) é obrigatória")
        if not (value.get("premiums") or []):
            raise InvalidConfiguration("pricing.reference_premiums: defina pelo menos uma tarifa")
