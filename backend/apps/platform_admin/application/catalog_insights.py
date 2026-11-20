"""Ajudas para gerir o catálogo da plataforma (parâmetros gerais, tabelas de
referência e modelos do fornecedor):

- exportar a versão em vigor para Excel, para a editar e propor de novo;
- diferenças de uma versão pendente face à que está em vigor;
- impacto: que seguradoras e fórmulas usam uma tabela, que seguradoras
  adotaram um modelo, quantas seguradoras um parâmetro afeta;
- a lista única de tudo o que está à espera de aprovação."""
from __future__ import annotations

import io
import json
import re
from typing import Any

from apps.foundation.infrastructure.models import PlatformParameterVersion, PlatformReferenceTableVersion
from apps.foundation.infrastructure.models import PlatformTemplateVersion, Tenant


def _active_tenants() -> dict[str, str]:
    return {str(k): v for k, v in Tenant.objects.filter(status="ACTIVE").values_list("id", "name")}


# ----------------------------------------------------- tabelas de referência
def table_version(code: str, version_no: int | None) -> PlatformReferenceTableVersion | None:
    from apps.foundation.application import platform_reference_service as service

    if version_no:
        return PlatformReferenceTableVersion.objects.filter(code=code, version_no=version_no).first()
    return service.effective_version(code) or PlatformReferenceTableVersion.objects.filter(code=code) \
        .order_by("-version_no").first()


def table_xlsx(code: str, version_no: int | None = None) -> tuple[bytes, str] | None:
    """Excel da tabela (uma coluna por coluna da tabela, cabeçalho = nome
    da coluna), no mesmo formato que o «Propor tabela» importa."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    version = table_version(code, version_no)
    if version is None:
        return None
    columns = version.columns_json or []
    book = Workbook()
    sheet = book.active
    sheet.title = code[:31]
    sheet.append([c.get("label") or c["code"] for c in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in version.rows_json or []:
        sheet.append([row.get(c["code"]) for c in columns])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue(), f"{code}-v{version.version_no}.xlsx"


def _rows_by_key(version: PlatformReferenceTableVersion | None) -> dict[str, dict[str, Any]]:
    if version is None:
        return {}
    return {str(row.get(version.key_column)): row for row in version.rows_json or []}


def table_usage(code: str) -> dict[str, Any]:
    """Seguradoras e fórmulas que chamam `tabela("code", …)`."""
    from apps.business_config.infrastructure.models import BusinessConfiguration

    pattern = re.compile(r"tabela\(\s*[\"']" + re.escape(code) + r"[\"']")
    names = {str(k): v for k, v in Tenant.objects.values_list("id", "name")}
    tenants: dict[str, set[str]] = {}
    for tenant_id, value in BusinessConfiguration.all_tenants.filter(
        config_key="pricing.formulas", status__in=("PUBLISHED", "PENDING_APPROVAL", "DRAFT")
    ).values_list("tenant_id", "value_json"):
        for rule in (value or {}).get("rules") or []:
            if pattern.search(str(rule.get("expression") or "")):
                tenants.setdefault(str(tenant_id), set()).add(str(rule.get("code") or rule.get("name") or "?"))
    return {
        "tenants": [{"tenantId": tid, "tenantName": names.get(tid), "formulas": sorted(codes)}
                    for tid, codes in sorted(tenants.items(), key=lambda item: names.get(item[0]) or "")],
        "tenantCount": len(tenants),
        "formulaCount": sum(len(codes) for codes in tenants.values()),
    }


def table_diff(code: str, version_no: int) -> dict[str, Any]:
    from apps.foundation.application import platform_reference_service as service

    target = PlatformReferenceTableVersion.objects.filter(code=code, version_no=version_no).first()
    if target is None:
        raise LookupError(f"A tabela '{code}' não tem a versão {version_no}")
    base = service.effective_version(code)
    if base is not None and base.version_no == target.version_no:
        base = None
    old, new = _rows_by_key(base), _rows_by_key(target)
    old_cols = [c["code"] for c in (base.columns_json if base else [])]
    new_cols = [c["code"] for c in target.columns_json or []]
    changed = []
    for key in sorted(set(old) & set(new)):
        diffs = [{"column": col, "before": old[key].get(col), "after": new[key].get(col)}
                 for col in sorted(set(old[key]) | set(new[key])) if str(old[key].get(col)) != str(new[key].get(col))]
        if diffs:
            changed.append({"key": key, "changes": diffs})
    added = [new[k] for k in sorted(set(new) - set(old))]
    removed = [old[k] for k in sorted(set(old) - set(new))]
    return {
        "code": code, "versionNo": target.version_no, "baseVersionNo": base.version_no if base else None,
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed),
                    "unchanged": len(set(old) & set(new)) - len(changed)},
        "columnsAdded": [c for c in new_cols if c not in old_cols],
        "columnsRemoved": [c for c in old_cols if c not in new_cols],
        "added": added[:100], "removed": removed[:100], "changed": changed[:100],
        "impact": table_usage(code),
    }


# ---------------------------------------------------------- modelos do fornecedor
def _leaf_rows(value: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        out: list[tuple[str, Any]] = []
        for key, item in value.items():
            out += _leaf_rows(item, f"{path}.{key}" if path else str(key))
        return out
    if isinstance(value, list):
        out = []
        for index, item in enumerate(value):
            out += _leaf_rows(item, f"{path}[{index}]")
        return out
    return [(path, value)]


def template_xlsx(code: str, version_no: int | None = None) -> tuple[bytes, str] | None:
    """Excel de 3 colunas (chave de configuração, caminho, valor), o mesmo
    formato que «Importar de Excel» lê."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    qs = PlatformTemplateVersion.objects.filter(code=code)
    version = qs.filter(version_no=version_no).first() if version_no else (
        qs.filter(status="PUBLISHED").order_by("-version_no").first() or qs.order_by("-version_no").first()
    )
    if version is None:
        return None
    book = Workbook()
    sheet = book.active
    sheet.title = "Modelo"
    sheet.append(["Chave de configuração", "Caminho", "Valor"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    content = version.content_json or {}
    for key, value in sorted((content.get("configurations") or {}).items()):
        for path, leaf in _leaf_rows(value):
            sheet.append([key, path, "TRUE" if leaf is True else "FALSE" if leaf is False else leaf])
    sheet.append(["marketProducts", "", "TRUE" if content.get("marketProducts") else "FALSE"])
    for column, width in zip("ABC", (30, 45, 40)):
        sheet.column_dimensions[column].width = width
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue(), f"{code}-v{version.version_no}.xlsx"


def template_usage(code: str) -> dict[str, Any]:
    from apps.business_config.infrastructure.models import BusinessConfiguration

    names = {str(k): v for k, v in Tenant.objects.values_list("id", "name")}
    rows = BusinessConfiguration.all_tenants.filter(metadata_json__adoptedFromTemplate__code=code) \
        .values_list("tenant_id", "metadata_json")
    adopted: dict[str, set[int]] = {}
    for tenant_id, meta in rows:
        adopted.setdefault(str(tenant_id), set()).add(int(((meta or {}).get("adoptedFromTemplate") or {}).get("versionNo") or 0))
    return {
        "tenants": [{"tenantId": tid, "tenantName": names.get(tid), "versions": sorted(v)}
                    for tid, v in sorted(adopted.items(), key=lambda item: names.get(item[0]) or "")],
        "tenantCount": len(adopted),
        "note": "As seguradoras que já adotaram o modelo não mudam sozinhas: têm de adotar a versão nova.",
    }


def template_diff(code: str, version_no: int) -> dict[str, Any]:
    target = PlatformTemplateVersion.objects.filter(code=code, version_no=version_no).first()
    if target is None:
        raise LookupError(f"O modelo '{code}' não tem a versão {version_no}")
    base = PlatformTemplateVersion.objects.filter(code=code, status="PUBLISHED").exclude(id=target.id) \
        .order_by("-version_no").first()
    old = (base.content_json or {}).get("configurations") or {} if base else {}
    new = (target.content_json or {}).get("configurations") or {}
    changed = []
    for key in sorted(set(old) & set(new)):
        before, after = dict(_leaf_rows(old[key])), dict(_leaf_rows(new[key]))
        diffs = [{"path": p, "before": before.get(p), "after": after.get(p)}
                 for p in sorted(set(before) | set(after)) if before.get(p) != after.get(p)]
        if diffs:
            changed.append({"configKey": key, "changes": diffs[:50], "changeCount": len(diffs)})
    return {
        "code": code, "versionNo": target.version_no, "baseVersionNo": base.version_no if base else None,
        "summary": {"added": len(set(new) - set(old)), "removed": len(set(old) - set(new)), "changed": len(changed)},
        "configKeysAdded": sorted(set(new) - set(old)), "configKeysRemoved": sorted(set(old) - set(new)),
        "changed": changed, "impact": template_usage(code),
    }


def template_catalog() -> list[dict[str, Any]]:
    """Para o assistente: as configurações que cada tipo de modelo pode
    trazer, com o nome e o formulário de cada uma."""
    from apps.business_config.application.platform_templates import KIND_KEYS, KIND_LABELS, KINDS
    from apps.business_config.domain.catalog import CONFIG_CATALOG
    from apps.business_config.domain.form_schemas import get_form_schema

    out = []
    for kind in KINDS:
        allowed = KIND_KEYS[kind]
        keys = [entry for entry in CONFIG_CATALOG if allowed is None or entry["key"] in allowed]
        out.append({
            "kind": kind, "label": KIND_LABELS[kind], "description": KIND_DESCRIPTIONS[kind],
            "configurations": [{"key": e["key"], "label": e["label"], "formSchema": get_form_schema(e["key"])}
                               for e in keys],
        })
    return out


KIND_DESCRIPTIONS = {
    "PRODUCT": "Um produto completo: planos, coberturas, regras e impostos. Pode também criar os produtos e planos "
               "de mercado de referência.",
    "ACTUARIAL_MODEL": "O modelo atuarial de referência (pressupostos de cálculo do prémio) e o fracionamento.",
    "FORMULA_SET": "Fórmulas de tarifação prontas a usar (por exemplo, prémio mínimo por pessoa).",
    "COVERAGE_LIBRARY": "Coberturas, capitais, carências, exclusões e co-participações, sem tarifa.",
}
SEGMENT_LABELS = {
    "SAU": "SAU — Seguro de Saúde Individual e Familiar",
    "SAG": "SAG — Seguro de Saúde de Grupo (empresas)",
}


# --------------------------------------------------------- parâmetros gerais
def parameter_impact(code: str) -> dict[str, Any]:
    from apps.foundation.domain.system_parameters import DEFINITIONS, PLATFORM_DEFAULT
    from apps.foundation.infrastructure.models import SystemParameter

    tenants = _active_tenants()
    definition = DEFINITIONS.get(code)
    if definition is None:
        return {"tenantCount": 0, "note": ""}
    if definition.level == PLATFORM_DEFAULT:
        overriding = {str(t) for t in SystemParameter.all_tenants.filter(code=code).values_list("tenant_id", flat=True)}
        affected = [t for t in tenants if t not in overriding]
        return {"tenantCount": len(affected),
                "note": f"Afeta {len(affected)} de {len(tenants)} seguradora(s) ativa(s); "
                        f"{len(tenants) - len(affected)} têm valor próprio (dentro dos limites)."}
    return {"tenantCount": len(tenants), "note": f"Obrigatório: afeta todas as {len(tenants)} seguradora(s) ativa(s)."}


# ------------------------------------------------------- pendentes de aprovação
def _short(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= 80 else text[:77] + "…"


def pending(*, admin_names: dict[str, str]) -> list[dict[str, Any]]:
    from apps.foundation.domain.system_parameters import DEFINITIONS

    items: list[dict[str, Any]] = []
    for v in PlatformParameterVersion.objects.filter(status="PENDING_APPROVAL").order_by("created_at"):
        definition = DEFINITIONS.get(v.code)
        items.append({
            "area": "PARAMETER", "areaLabel": "Parâmetro geral", "code": v.code,
            "name": getattr(definition, "description", None) or v.code, "versionNo": v.version_no,
            "summary": f"Novo valor: {_short(v.value_json)}", "reason": v.reason,
            "createdBy": v.created_by, "createdByName": admin_names.get(str(v.created_by)),
            "createdAt": v.created_at, "effectiveFrom": v.effective_from,
            "impact": parameter_impact(v.code)["note"],
        })
    for v in PlatformReferenceTableVersion.objects.filter(status="PENDING_APPROVAL").order_by("created_at"):
        diff = table_diff(v.code, v.version_no)
        s = diff["summary"]
        usage = diff["impact"]
        items.append({
            "area": "REFERENCE_TABLE", "areaLabel": "Tabela de referência", "code": v.code, "name": v.name,
            "versionNo": v.version_no,
            "summary": (f"Linhas novas: {s['added']} · alteradas: {s['changed']} · removidas: {s['removed']}"
                        if diff["baseVersionNo"] else f"Tabela nova com {s['added']} linha(s)"),
            "reason": v.reason, "createdBy": v.created_by, "createdByName": admin_names.get(str(v.created_by)),
            "createdAt": v.created_at, "effectiveFrom": v.effective_from,
            "impact": (f"Usada por {usage['tenantCount']} seguradora(s) em {usage['formulaCount']} fórmula(s)"
                       if usage["tenantCount"] else "Ainda não é usada em nenhuma fórmula"),
        })
    for v in PlatformTemplateVersion.objects.filter(status="PENDING_APPROVAL").order_by("created_at"):
        diff = template_diff(v.code, v.version_no)
        s = diff["summary"]
        usage = diff["impact"]
        items.append({
            "area": "TEMPLATE", "areaLabel": "Modelo do fornecedor", "code": v.code, "name": v.name,
            "versionNo": v.version_no,
            "summary": (f"Configurações novas: {s['added']} · alteradas: {s['changed']} · removidas: {s['removed']}"
                        if diff["baseVersionNo"] else f"Modelo novo com {s['added']} configuração(ões)"),
            "reason": v.reason, "createdBy": v.created_by, "createdByName": admin_names.get(str(v.created_by)),
            "createdAt": v.created_at, "effectiveFrom": v.effective_from,
            "impact": (f"Adotado por {usage['tenantCount']} seguradora(s); só muda para quem adotar a versão nova"
                       if usage["tenantCount"] else "Ainda não foi adotado por nenhuma seguradora"),
        })
    items.sort(key=lambda item: item["createdAt"])
    return items
