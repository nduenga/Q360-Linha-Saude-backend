"""Modelo de documento da proposta (R8) — configurável pelo GTE sem código.

O corpo do modelo (`DocumentTemplateVersion.storage_ref`) é JSON:

    {
      "title": "Proposta de Seguro de Saúde {{quote.number}}",
      "intro": "Exmo(a). Sr(a). {{client.name}}, ...",
      "footer": "...",
      "disclaimer": "...",          # opcional; por omissão o aviso do PDF
      "sections": ["summary", "population", "coverages", "premium", ...]
    }

Os textos aceitam `{{variáveis}}` de uma lista fechada (`VARIABLES`); as
secções são escolhidas e ordenadas pelo GTE de uma lista fechada
(`SECTIONS`). Um modelo com secções ou variáveis desconhecidas é recusado ao
criar/editar — nunca fica um documento a sair com `{{buraco}}`.

Um `storage_ref` que não seja JSON (os modelos antigos, só um apontador) usa
o desenho por omissão.
"""
from __future__ import annotations

import json
import re
from typing import Any

from apps.foundation.domain.problem import DomainProblem

SECTIONS: dict[str, str] = {
    "summary": "Resumo da proposta (cliente, plano, vigência, validade)",
    "population": "Pessoas seguras e decisões de subscrição",
    "coverages": "Coberturas, capitais e participação",
    "premium": "Prémio e ajustes",
    "waiting": "Períodos de carência",
    "preexisting": "Doenças preexistentes",
    "exclusions": "Exclusões",
    "conditions": "Condições (pré-autorização, evacuação, renovação, grupo)",
    "signature": "Aceitação / assinatura",
}

VARIABLES: dict[str, str] = {
    "quote.number": "Número da cotação",
    "quote.date": "Data da cotação",
    "quote.validUntil": "Válida até",
    "quote.type": "Tipo (Novo negócio / Renovação)",
    "document.number": "Número do documento",
    "document.date": "Data de emissão",
    "client.name": "Nome do cliente/tomador",
    "client.nif": "NIF do cliente",
    "plan.name": "Nome do plano",
    "plan.product": "Nome do produto",
    "plan.segment": "Segmento (Individual e Familiar / Grupo)",
    "premium.total": "Prémio total",
    "premium.currency": "Moeda",
    "scenario.name": "Nome do cenário",
    "insured.count": "Número de pessoas seguras",
}

DEFAULT_DISCLAIMER = (
    "Os valores em Kz são indicativos: a composição de cada plano varia por seguradora e deve ser confirmada "
    "nas Condições Gerais, Especiais e na Tabela de Benefícios."
)

DEFAULT_TEMPLATE: dict[str, Any] = {
    "title": "Proposta de Seguro de Saúde {{quote.number}}",
    "intro": (
        "Exmo(a). Sr(a). {{client.name}}, apresentamos a proposta de seguro de saúde para o plano "
        "{{plan.name}}, válida até {{quote.validUntil}}."
    ),
    "footer": "Documento {{document.number}} emitido em {{document.date}}.",
    "disclaimer": DEFAULT_DISCLAIMER,
    "sections": ["summary", "population", "coverages", "premium", "waiting", "preexisting", "exclusions", "conditions", "signature"],
}

_VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")
_TEXT_KEYS = ("title", "intro", "footer", "disclaimer")


class InvalidTemplateError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def default_body() -> str:
    return json.dumps(DEFAULT_TEMPLATE, ensure_ascii=False, indent=2)


def extract_variables(text: str) -> list[str]:
    return _VARIABLE_PATTERN.findall(text or "")


def render_text(text: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match) -> str:
        value = variables.get(match.group(1))
        return "" if value is None else str(value)

    return _VARIABLE_PATTERN.sub(replace, text or "")


def is_structured(storage_ref: str) -> bool:
    return storage_ref.lstrip().startswith("{")


def parse_template(storage_ref: str | None) -> dict[str, Any]:
    """The effective template: the body when it is a valid structured one,
    the default layout otherwise (legacy pointer-only templates)."""
    if not storage_ref or not is_structured(storage_ref):
        return dict(DEFAULT_TEMPLATE)
    try:
        body = json.loads(storage_ref)
    except json.JSONDecodeError:
        return dict(DEFAULT_TEMPLATE)
    return {**DEFAULT_TEMPLATE, **{k: v for k, v in body.items() if k in (*_TEXT_KEYS, "sections")}}


def validate_template_body(storage_ref: str) -> None:
    """Strict validation of a structured body (a non-JSON `storage_ref` is
    the legacy pointer form and is accepted as is)."""
    if not is_structured(storage_ref):
        return
    try:
        body = json.loads(storage_ref)
    except json.JSONDecodeError as exc:
        raise InvalidTemplateError(f"O corpo do modelo não é JSON válido: {exc.msg}") from exc
    if not isinstance(body, dict):
        raise InvalidTemplateError("O corpo do modelo tem de ser um objeto JSON")
    unknown_keys = set(body) - {*_TEXT_KEYS, "sections"}
    if unknown_keys:
        raise InvalidTemplateError(f"Campo(s) do modelo desconhecido(s): {sorted(unknown_keys)}")
    for key in _TEXT_KEYS:
        if key in body:
            if not isinstance(body[key], str):
                raise InvalidTemplateError(f"O campo '{key}' do modelo tem de ser texto")
            unknown = sorted({v for v in extract_variables(body[key]) if v not in VARIABLES})
            if unknown:
                raise InvalidTemplateError(f"O campo '{key}' do modelo usa variável(is) desconhecida(s): {unknown}; permitidas: {sorted(VARIABLES)}")
    sections = body.get("sections", DEFAULT_TEMPLATE["sections"])
    if not isinstance(sections, list) or not sections:
        raise InvalidTemplateError("As secções ('sections') do modelo têm de ser uma lista não vazia")
    bad = [s for s in sections if s not in SECTIONS]
    if bad:
        raise InvalidTemplateError(f"Secção(ões) desconhecida(s) {bad}; permitidas: {sorted(SECTIONS)}")
    if len(set(sections)) != len(sections):
        raise InvalidTemplateError("As secções ('sections') do modelo têm duplicados")
