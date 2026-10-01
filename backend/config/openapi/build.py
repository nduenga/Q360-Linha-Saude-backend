"""Builds the OpenAPI contract from the code and merges it into the approved
ART-006 file.

    python manage.py build_openapi            # writes both files
    python manage.py build_openapi --check    # fails if they are out of date

- `backend/schema.yml`: the generated, as-implemented contract (OpenAPI 3.1).
- `docs/artifacts/ART-006-openapi/Q360_MVP_ART_006_OpenAPI_Integral_v1.0.yml`:
  the approved contract. Its `info`, `servers`, `security` and untouched
  component schemas are kept; every implemented operation is replaced by the
  generated one (except the few in `registry.KEEP_CONTRACT`, whose approved
  description is richer); operations the contract described but that do not
  exist in the API are removed (they were planned under different paths and
  were never built).
"""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml
from drf_spectacular.generators import SchemaGenerator

from config.openapi.registry import KEEP_CONTRACT

REPO = Path(__file__).resolve().parents[3]
GENERATED = REPO / "backend" / "schema.yml"
CONTRACT = REPO / "docs" / "artifacts" / "ART-006-openapi" / "Q360_MVP_ART_006_OpenAPI_Integral_v1.0.yml"
METHODS = ("get", "put", "post", "delete", "patch")
CONTRACT_VERSION = "1.4.0"
CHANGELOG = (
    " v1.4.0 alinha o contrato com a API implementada: todas as operações passam a ser geradas a partir do código "
    "(pedido, resposta, parâmetros, cabeçalho Idempotency-Key, scopes/permissões e erros application/problem+json) e "
    "acrescenta biblioteca de coberturas versionada, configuração de planos e participação A–E, ajustes, cenários e "
    "comparação, versões/renovação/indexação, requisitos de subscrição, sinistralidade, rollback/diff/simulação de impacto "
    "de configurações, parâmetros globais, propostas PDF/DOCX/HTML, apólices, portal do cliente e contas de staff. "
    "Os caminhos que o contrato v1.3.0 previa mas que não foram construídos foram removidos."
)


def _problem_media(spec: dict[str, Any]) -> None:
    for item in spec["paths"].values():
        for method, op in item.items():
            if method not in METHODS:
                continue
            for code, resp in op.get("responses", {}).items():
                if str(code).startswith(("4", "5")) and "content" in resp and "application/json" in resp["content"]:
                    schema = resp["content"].pop("application/json")
                    resp["content"]["application/problem+json"] = schema


def generate() -> dict[str, Any]:
    spec = SchemaGenerator().get_schema(request=None, public=True)
    spec = copy.deepcopy(dict(spec))
    _problem_media(spec)
    spec["components"].setdefault("securitySchemes", {})
    spec["components"]["securitySchemes"].setdefault(
        "customerPortalBearer",
        {"type": "http", "scheme": "bearer", "bearerFormat": "JWT", "description": "Sessão do portal do cliente (OTP por email)."},
    )
    return spec


def _norm(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def merge(generated: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(contract)
    old_paths = contract["paths"]
    old_by_norm = {_norm(p): (p, item) for p, item in old_paths.items()}
    new_paths: dict[str, Any] = {}
    for path, item in generated["paths"].items():
        merged: dict[str, Any] = {}
        existing = old_by_norm.get(_norm(path), (None, {}))[1]
        for method in METHODS:
            if method not in item:
                continue
            op = copy.deepcopy(item[method])
            if (path, method) in KEEP_CONTRACT and method in existing:
                op = copy.deepcopy(existing[method])
            merged[method] = op
        if "parameters" in item:
            merged["parameters"] = item["parameters"]
        new_paths[path] = merged
    out["paths"] = dict(sorted(new_paths.items()))

    schemas = out.setdefault("components", {}).setdefault("schemas", {})
    for name, schema in generated["components"].get("schemas", {}).items():
        schemas[name] = schema
    sec = out["components"].setdefault("securitySchemes", {})
    sec.update({k: v for k, v in generated["components"].get("securitySchemes", {}).items() if k not in sec})
    for key in ("parameters", "responses"):
        for name, value in generated["components"].get(key, {}).items():
            out["components"].setdefault(key, {}).setdefault(name, value)

    tags = [{"name": t} for t in sorted({t for item in new_paths.values() for op in item.values() if isinstance(op, dict) for t in op.get("tags", [])})]
    out["tags"] = tags
    out["info"]["version"] = CONTRACT_VERSION
    description = out["info"].get("description", "")
    if CHANGELOG.strip() not in description:
        out["info"]["description"] = re.sub(r"\s*v1\.4\.0 alinha.*$", "", description, flags=re.S).rstrip() + " " + CHANGELOG.strip()
    return out


def dump(spec: dict[str, Any]) -> str:
    return yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=110)


def build(*, write: bool = True) -> tuple[str, str]:
    generated = generate()
    generated["info"]["title"] = "Q360 Health Underwriting & Pricing Core API (as implemented)"
    generated["info"]["version"] = CONTRACT_VERSION
    generated["info"]["description"] = "Contrato gerado a partir do código. O contrato aprovado é ART-006 (docs/artifacts/ART-006-openapi)."
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    merged = merge(generated, contract)
    texts = (dump(generated), dump(merged))
    if write:
        GENERATED.write_text(texts[0], encoding="utf-8")
        CONTRACT.write_text(texts[1], encoding="utf-8")
    return texts
