"""Forma de uma configuração: o formulário guarda as secções simples (não
repetíveis) como objetos aninhados (`{"group": {"minimum_members": 5}}`); os
motores lêem os campos ao nível de topo. `flatten` aceita as duas formas."""
from __future__ import annotations

from typing import Any

from apps.business_config.domain.form_schemas import get_form_schema


def flatten(key: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    flat = dict(value)
    for section in get_form_schema(key)["sections"]:
        if section.get("repeatable"):
            continue
        nested = value.get(section["key"])
        if isinstance(nested, dict):
            flat.pop(section["key"], None)
            for name, item in nested.items():
                flat.setdefault(name, item)
    return flat
