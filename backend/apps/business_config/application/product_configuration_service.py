"""Configuração de um produto em cascata seguradora → produto → plano.

`describe_product_configuration` mostra, para cada configuração que pode ter
versão de produto, de onde vem o valor que vale hoje nesse produto:

- `PRODUCT`: o produto tem a sua versão publicada (`<chave>@<id>`);
- `GENERAL`: o produto herda a versão geral da seguradora;
- `NONE`: não há nenhuma versão publicada.

`copy_configuration` cria rascunhos de produto a partir da configuração geral
ou da de outro produto, para ninguém começar do zero nem herdar por acidente.
Os rascunhos seguem o ciclo de sempre (submissão e aprovação por outra
pessoa). Para o produto voltar a herdar a geral, retira-se a versão do
produto (`retire`)."""
from __future__ import annotations

import copy
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.business_config.application.service import create_configuration
from apps.business_config.application.tariff_service import key_state
from apps.business_config.domain.catalog import AREA_LABELS, CATALOG_BY_KEY, CONFIG_CATALOG, area_of
from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.form_schemas import get_form_schema
from apps.business_config.domain.product_setup import config_key as product_setup_key
from apps.business_config.domain.scope import PRODUCT_SCOPED_KEYS, product_key
from apps.business_config.infrastructure.models import BusinessConfiguration

PRODUCT, GENERAL, NONE = "PRODUCT", "GENERAL", "NONE"
SOURCES = (GENERAL, PRODUCT)
# Campos de plano nos formulários: na vista do produto, as opções são os
# planos desse produto (e não a lista de exemplo da configuração geral).
_PLAN_FIELDS = {"plan", "included_in_plans", "applies_to"}
_OPEN = ("DRAFT", "REJECTED", "PENDING_APPROVAL")


def _plan_choices(product) -> tuple[list[str], dict[str, str]]:
    plans = list(product.plans.order_by("code"))
    return [p.code for p in plans], {p.code: f"{p.name} ({p.code})" for p in plans}


def product_form_schema(base: str, product) -> dict[str, Any]:
    schema = copy.deepcopy(get_form_schema(base))
    options, labels = _plan_choices(product)
    for section in schema.get("sections", []):
        for field in section.get("fields", []):
            if field.get("name") in _PLAN_FIELDS:
                field["options"] = options
                field["optionLabels"] = labels
    return schema


def describe_product_configuration(product) -> dict[str, Any]:
    day = timezone.localdate()
    items = []
    for base in PRODUCT_SCOPED_KEYS:
        entry = CATALOG_BY_KEY[base]
        own = key_state(product_key(base, product.id), day)
        general = key_state(base, day)
        source = PRODUCT if own["published"] else GENERAL if general["published"] else NONE
        area = area_of(base)
        behind = _general_changed_since_copy(own, general, base) if source == PRODUCT else None
        items.append({
            "configKey": base,
            "productConfigKey": own["configKey"],
            "label": entry["label"],
            "category": entry["category"],
            "area": area,
            "areaLabel": AREA_LABELS[area],
            "source": source,
            "product": own,
            "general": general,
            "generalChangedSinceCopy": behind,
            "formSchema": product_form_schema(base, product),
        })
    setup = key_state(product_setup_key(product.id), day)
    plan_options, _ = _plan_choices(product)
    return {
        "productId": str(product.id),
        "productCode": product.code,
        "productName": product.name,
        "plans": [{"id": str(p.id), "code": p.code, "name": p.name, "status": p.status}
                  for p in product.plans.order_by("code")],
        "planOptions": plan_options,
        "items": items,
        "pricingSetup": setup,
        "generalOnly": [
            {"configKey": x["key"], "label": x["label"], "area": area_of(x["key"])}
            for x in CONFIG_CATALOG if x["key"] not in PRODUCT_SCOPED_KEYS
        ],
    }


def _general_changed_since_copy(own: dict[str, Any], general: dict[str, Any], base: str) -> dict[str, Any] | None:
    """A versão do produto substitui a geral por inteiro, por isso uma
    alteração posterior à geral não chega ao produto. Quando a versão do
    produto foi copiada da geral e a geral publicada já é outra, devolve as
    duas versões para o ecrã avisar e propor nova cópia; senão None."""
    if not own["published"] or not general["published"]:
        return None
    row = BusinessConfiguration.objects.filter(id=own["published"]["configurationId"]).values_list("metadata_json", flat=True).first()
    origin = (row or {}).get("copiedFrom") or {}
    if origin.get("configKey") != base or origin.get("versionNo") is None:
        return None
    if origin["versionNo"] >= general["published"]["versionNo"]:
        return None
    return {"copiedVersionNo": origin["versionNo"], "generalVersionNo": general["published"]["versionNo"]}


def _published_value(key: str) -> BusinessConfiguration | None:
    day = timezone.localdate()
    state = key_state(key, day)["published"]
    return BusinessConfiguration.objects.get(id=state["configurationId"]) if state else None


@transaction.atomic
def copy_configuration(product, *, source: str = GENERAL, source_product=None,
                       keys: list[str] | None = None, include_pricing_setup: bool = True) -> dict[str, Any]:
    """Rascunhos de produto copiados da configuração geral (`GENERAL`) ou de
    outro produto (`PRODUCT`). Uma chave que já tem rascunho ou versão à
    espera de aprovação neste produto, ou que não tem versão publicada na
    origem, fica de fora (com o motivo)."""
    if source not in SOURCES:
        raise InvalidConfiguration(f"Origem inválida (use {list(SOURCES)}).")
    if source == PRODUCT:
        if source_product is None:
            raise InvalidConfiguration("Indique o produto de onde copiar a configuração.")
        if source_product.id == product.id:
            raise InvalidConfiguration("O produto de origem tem de ser outro produto.")
    unknown = sorted(set(keys or []) - set(PRODUCT_SCOPED_KEYS))
    if unknown:
        raise InvalidConfiguration(f"Configurações sem versão por produto: {unknown}")
    chosen = [k for k in PRODUCT_SCOPED_KEYS if not keys or k in keys]
    today = timezone.localdate()
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    pairs = []
    for base in chosen:
        if source == GENERAL:
            pairs.append((base, base, product_key(base, product.id)))
        else:
            # A origem é o que vale hoje no outro produto: a versão dele ou a geral.
            origin = product_key(base, source_product.id)
            pairs.append((base, origin if _published_value(origin) else base, product_key(base, product.id)))
    if source == PRODUCT and include_pricing_setup:
        pairs.append(("product.pricing_setup", product_setup_key(source_product.id), product_setup_key(product.id)))

    for base, origin, target in pairs:
        if BusinessConfiguration.objects.filter(config_key=target, status__in=_OPEN).exists():
            skipped.append({"configKey": base, "reason": "Já existe um rascunho ou uma versão à espera de aprovação neste produto."})
            continue
        published = _published_value(origin)
        if published is None:
            skipped.append({"configKey": base, "reason": "Não há versão publicada na origem."})
            continue
        draft = create_configuration(
            None, target, copy.deepcopy(published.value_json), today,
            metadata={"copiedFrom": {"configKey": published.config_key, "configurationId": str(published.id),
                                     "versionNo": published.version_no}},
        )
        created.append({"configKey": base, "productConfigKey": target, "configurationId": str(draft.id),
                        "versionNo": draft.version_no, "copiedFrom": published.config_key})
    return {"productId": str(product.id), "source": source,
            "sourceProductId": str(source_product.id) if source_product is not None else None,
            "created": created, "skipped": skipped}
