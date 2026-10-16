"""Catálogo único das variáveis que o tenant pode usar nas fórmulas e regras.

Junta numa só resposta o que antes estava espalhado por vários catálogos:
  - as variáveis do motor de cada fase das fórmulas de tarifação (PERSON,
    QUOTE) e as funções/operadores permitidos;
  - os parâmetros e valores auxiliares (VALUE) do conjunto `pricing.formulas`
    publicado em vigor;
  - os grupos, opções, campos numéricos, fórmulas e variáveis do sistema da
    configuração de tarifação de um produto (`?productId=`);
  - os campos das condições das regras «Quando… então…»;
  - as constantes do fornecedor (câmbio, inflação, taxas legais…) e as
    tabelas de referência em vigor, usáveis em todas as fórmulas.
Cada entrada diz onde pode ser usada (`usableIn`). Só aparece o que o motor
efetivamente lê: nada de variáveis decorativas.
"""
from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.business_config.application import product_setup_service
from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.domain import custom_rules
from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.formula_engine import ALLOWED_FUNCTIONS, ALLOWED_OPERATORS
from apps.business_config.domain.formulas import CONFIG_KEY, STAGES, SYSTEM_VARIABLES, parse_formula_set
from apps.business_config.domain.product_setup import parse_product_setup
from apps.foundation.application import platform_parameter_service, platform_reference_service
from apps.foundation.domain.system_parameters import DEFINITIONS, PLATFORM_CONSTANTS

_PRODUCT_KINDS = {
    "GROUP": "PRODUCT_GROUP",
    "OPTION": "PRODUCT_OPTION",
    "FIELD": "PRODUCT_FIELD",
    "FORMULA": "PRODUCT_FORMULA",
    "SYSTEM": "PRODUCT_SYSTEM",
}


def _constant_value(code: str) -> str | None:
    value = platform_parameter_service.platform_value(code)
    return None if value is None else str(value)


def _first_value_column(version) -> str:
    for column in version.columns_json:
        if column["code"] != version.key_column and column.get("type") == "NUMBER":
            return column["code"]
    return version.key_column


def _version(row) -> dict[str, Any]:
    return {"configurationId": str(row.id), "configKey": row.config_key, "versionNo": row.version_no}


def _pricing_formula_variables() -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    variables: list[dict[str, Any]] = []
    for stage in STAGES:
        for name, meta in SYSTEM_VARIABLES[stage].items():
            variables.append({"token": name, "label": meta["label"], "unit": meta["unit"], "source": "SYSTEM",
                              "usableIn": [f"PRICING_FORMULAS:{stage}"]})
    row = BusinessConfigurationResolver.get(CONFIG_KEY, effective_date=timezone.localdate())
    if row is None:
        return variables, None, None
    try:
        formula_set = parse_formula_set(row.value_json)
    except InvalidConfiguration as exc:  # versão antiga gravada antes da validação
        return variables, _version(row), str(exc)
    for parameter in formula_set.parameters:
        variables.append({"token": parameter.code, "label": parameter.label or parameter.code, "unit": parameter.unit,
                          "value": str(parameter.value), "source": "PARAMETER",
                          "usableIn": [f"PRICING_FORMULAS:{stage}" for stage in STAGES]})
    for formula in formula_set.formulas:
        if formula.target == "VALUE":
            variables.append({"token": formula.code, "label": formula.name, "unit": None, "source": "AUXILIARY",
                              "expression": formula.expression, "active": formula.active,
                              "usableIn": [f"PRICING_FORMULAS:{formula.stage}"]})
    return variables, _version(row), None


def _product_variables(product_id) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    row = product_setup_service.published(product_id)
    if row is None:
        row = product_setup_service.open_draft(product_id)
    if row is None:
        return [], None, None
    try:
        setup = parse_product_setup(row.value_json)
    except InvalidConfiguration as exc:
        return [], {**_version(row), "status": row.status}, str(exc)
    variables = [
        {**{k: v for k, v in token.items() if k != "kind"}, "source": _PRODUCT_KINDS[token["kind"]],
         "usableIn": ["PRODUCT_FORMULAS"]}
        for token in setup.tokens()
    ]
    return variables, {**_version(row), "status": row.status}, None


def variable_catalog(*, product_id=None, usable_in: str | None = None) -> dict[str, Any]:
    variables, formulas_version, formulas_error = _pricing_formula_variables()
    product_version = product_error = None
    if product_id is not None:
        product_variables, product_version, product_error = _product_variables(product_id)
        variables += product_variables
    all_formulas = [f"PRICING_FORMULAS:{stage}" for stage in STAGES] + ["PRODUCT_FORMULAS"]
    for name, code in sorted(PLATFORM_CONSTANTS.items()):
        definition = DEFINITIONS[code]
        variables.append({"token": name, "label": definition.description, "unit": definition.unit,
                          "value": _constant_value(code), "parameter": code, "source": "PLATFORM_CONSTANT",
                          "readOnly": True, "usableIn": all_formulas})
    for field in custom_rules.field_catalog()["fields"]:
        variables.append({"token": field["key"], "label": field["label"], "kind": field["kind"],
                          "options": field["options"], "source": "RULE_FIELD", "usableIn": ["RULE_CONDITIONS"],
                          "personOnly": field["personOnly"], "excludedStages": field["excludedStages"]})
    if usable_in:
        variables = [v for v in variables if any(u == usable_in or u.startswith(f"{usable_in}:") for u in v["usableIn"])]
    return {
        "variables": variables,
        "functions": [{"name": name, "description": text} for name, text in ALLOWED_FUNCTIONS.items()],
        "referenceTables": [
            {"code": v.code, "name": v.name, "versionNo": v.version_no, "keyColumn": v.key_column,
             "columns": v.columns_json, "example": f'tabela("{v.code}", chave, "{_first_value_column(v)}")'}
            for _, v in sorted(platform_reference_service.effective_tables().items())
        ],
        "operators": list(ALLOWED_OPERATORS),
        "sources": {
            "pricingFormulas": formulas_version,
            "pricingFormulasError": formulas_error,
            "productSetup": product_version,
            "productSetupError": product_error,
        },
    }
