"""Importação de um modelo do fornecedor a partir de um .xlsx — alternativa
ao JSON em bruto em `apps.business_config.application.platform_templates`
para quem não domina JSON.

O conteúdo de um modelo (`content.configurations = {configKey: valor}`) é
heterogéneo: cada `configKey` do catálogo (`apps.business_config.domain.
catalog`) tem a sua própria forma aninhada — não é uma tabela plana como
as tabelas de referência. Por isso o layout do Excel aqui é genérico, não
uma linha por registo: três colunas (chave de configuração, caminho,
valor), uma linha por valor folha; `_set_path` reconstrói qualquer
estrutura aninhada (objetos e listas) a partir do caminho, sem conhecer a
forma de cada `configKey`. Isto só produz o `content` candidato — a
validação de negócio continua a ser sempre `validate_content`/`validate`
(chamada em `platform_templates.propose`), nunca duplicada aqui.
"""
from __future__ import annotations

import re
from typing import Any

from apps.business_config.application.platform_templates import TemplateContentError
from apps.foundation.application.platform_reference_service import parse_workbook_preview

_TOKEN = re.compile(r"\.?([^.\[\]]+)|\[(\d+)\]")


def _coerce(raw: str) -> Any:
    """Texto de uma célula → bool/int/str. Nunca para float: dinheiro e
    percentagens viajam como decimal-string (convenção ART-006), e
    `decimal_value` aceita str OU int — nunca float — por isso um número
    inteiro vira `int` (serve tanto para um campo inteiro como para um
    decimal) e tudo o resto (incl. "50000.00") fica string."""
    text = raw.strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _set_path(root: dict, path: str, value: Any, *, context: str) -> None:
    tokens: list[tuple[str, Any]] = []
    for match in _TOKEN.finditer(path):
        if match.group(1) is not None:
            tokens.append(("key", match.group(1)))
        else:
            tokens.append(("idx", int(match.group(2))))
    if not tokens:
        raise TemplateContentError(f"{context}: caminho inválido '{path}'")
    cursor: Any = root
    for index, (kind, key) in enumerate(tokens):
        is_last = index == len(tokens) - 1
        next_kind = tokens[index + 1][0] if not is_last else None
        if kind == "key":
            if is_last:
                cursor[key] = value
            else:
                if not isinstance(cursor.get(key), (dict, list)):
                    cursor[key] = [] if next_kind == "idx" else {}
                cursor = cursor[key]
        else:
            if not isinstance(cursor, list):
                raise TemplateContentError(f"{context}: caminho '{path}' usa [índice] sobre algo que não é uma lista")
            while len(cursor) <= key:
                cursor.append(None)
            if is_last:
                cursor[key] = value
            else:
                if not isinstance(cursor[key], (dict, list)):
                    cursor[key] = [] if next_kind == "idx" else {}
                cursor = cursor[key]


def workbook_rows_to_content(headers: list[str], rows: list[list[str]]) -> dict[str, Any]:
    """`headers`/`rows` tal como devolvidos por `parse_workbook_preview` —
    espera exatamente 3 colunas: chave de configuração, caminho, valor.
    Uma linha com a chave especial `marketProducts` (sem caminho) define
    `content.marketProducts`; todas as outras acrescentam a
    `content.configurations[chave]`."""
    if len(headers) != 3:
        raise TemplateContentError(
            "A folha tem de ter exatamente 3 colunas: chave de configuração, caminho, valor "
            f"(tem {len(headers)})."
        )

    content: dict[str, Any] = {"configurations": {}}
    for row_index, row in enumerate(rows, start=2):
        config_key, path, raw_value = (list(row) + ["", "", ""])[:3]
        config_key = config_key.strip()
        path = path.strip()
        if not config_key:
            raise TemplateContentError(f"Linha {row_index}: falta a chave de configuração.")
        value = _coerce(raw_value)
        if config_key.lower() == "marketproducts":
            if not isinstance(value, bool):
                raise TemplateContentError(f"Linha {row_index}: 'marketProducts' tem de ser TRUE ou FALSE.")
            content["marketProducts"] = value
            continue
        if not path:
            raise TemplateContentError(f"Linha {row_index}: falta o caminho dentro de '{config_key}'.")
        target = content["configurations"].setdefault(config_key, {})
        _set_path(target, path, value, context=f"Linha {row_index} ({config_key})")
    return content


def parse_template_workbook(raw_bytes: bytes) -> dict[str, Any]:
    parsed = parse_workbook_preview(raw_bytes)
    return {
        "content": workbook_rows_to_content(parsed["headers"], parsed["rows"]),
        "truncated": parsed["truncated"],
    }


# Dados de teste: três planos, regras de grupo e de renovação — tudo passa
# o `validate_content`/`validate` reais (form_schemas de "product.plans",
# "group.rules" e "renewal.rules").
_EXAMPLE_ROWS = [
    *[
        row
        for index, (code, name, description, copayment) in enumerate([
            ("basico", "Básico", "Hospitalização e urgências", 20),
            ("standard", "Standard", "Básico com ambulatório e medicamentos", 15),
            ("premium", "Premium", "Standard com estomatologia, oftalmologia e evacuação", 10),
        ])
        for row in (
            ["product.plans", f"plans[{index}].code", code],
            ["product.plans", f"plans[{index}].name", name],
            ["product.plans", f"plans[{index}].description", description],
            ["product.plans", f"plans[{index}].active", "TRUE"],
            ["product.plans", f"plans[{index}].default_copayment_percent", copayment],
        )
    ],
    ["group.rules", "group.minimum_members", 5],
    ["group.rules", "group.below_minimum_behavior", "INDIVIDUAL"],
    ["group.rules", "group.mandatory_enrolment", "TRUE"],
    ["group.rules", "group.questionnaire_exemption_threshold", 20],
    ["renewal.rules", "renewal.automatic_renewal", "TRUE"],
    ["renewal.rules", "renewal.medical_inflation_percent", "8.50"],
    ["renewal.rules", "renewal.continuity_without_new_waiting_period", "TRUE"],
    ["marketProducts", "", "FALSE"],
]


def build_import_template() -> bytes:
    """.xlsx de exemplo, em memória, com as linhas de `_EXAMPLE_ROWS`."""
    import io

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Modelo"
    sheet.append(["chave (configKey)", "caminho (path)", "valor"])
    for row in _EXAMPLE_ROWS:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
