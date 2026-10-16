"""Fila única de aprovações do tenant: tudo o que espera pela segunda pessoa
(configurações de negócio, fórmulas, configuração de cada produto, regras),
com o que mudou face à versão publicada e se o utilizador atual pode
aprovar."""
from __future__ import annotations

from typing import Any

from django.db import models
from django.utils import timezone

from apps.business_config.application.readers import BusinessSnapshot
from apps.business_config.application.service import diff_values
from apps.business_config.domain.catalog import AREA_LABELS, CATALOG_BY_KEY, area_of
from apps.business_config.domain.product_setup import is_product_setup_key, product_id_of
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.application.context import CurrentActorProvider


def _label(key: str, products: dict[str, str]) -> str:
    if is_product_setup_key(key):
        return f"Configuração do produto {products.get(product_id_of(key), product_id_of(key))}"
    entry = CATALOG_BY_KEY.get(key)
    return entry["label"] if entry else key


def _can_approve(row: BusinessConfiguration, actor, rules: dict) -> tuple[bool, str | None]:
    actor_id = actor.actor_id if actor else None
    if row.created_by == actor_id and rules.get("four_eyes_required") is not False:
        return False, "Foi o utilizador atual que criou esta versão (aprovação por outra pessoa)."
    roles = {getattr(r, "value", r) for r in (actor.roles if actor else ())}
    allowed = set(rules.get("approval_roles") or [])
    if allowed and "ADMIN" not in roles and not roles & allowed:
        return False, f"O seu perfil não aprova configurações (perfis permitidos: {sorted(allowed | {'ADMIN'})})."
    return True, None


def pending_queue(*, area: str | None = None) -> dict[str, Any]:
    from apps.product.infrastructure.models import Product

    day = timezone.localdate()
    actor = CurrentActorProvider.get()
    rules = BusinessSnapshot.load().get("security.approval_rules") or {}
    pending = list(BusinessConfiguration.objects.filter(status="PENDING_APPROVAL").order_by("submitted_at", "created_at"))
    products = {str(p.id): p.name for p in Product.objects.filter(
        id__in=[product_id_of(r.config_key) for r in pending if is_product_setup_key(r.config_key)])}
    items = []
    for row in pending:
        row_area = area_of(row.config_key)
        if area and row_area != area:
            continue
        published = (
            BusinessConfiguration.objects.filter(config_key=row.config_key, status="PUBLISHED", effective_from__lte=day)
            .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=day))
            .order_by("-version_no").first()
        )
        changes = diff_values(published.value_json, row.value_json) if published else None
        can, why = _can_approve(row, actor, rules)
        items.append({
            "configurationId": str(row.id),
            "configKey": row.config_key,
            "label": _label(row.config_key, products),
            "area": row_area,
            "areaLabel": AREA_LABELS[row_area],
            "versionNo": row.version_no,
            "effectiveFrom": row.effective_from.isoformat() if row.effective_from else None,
            "createdBy": row.created_by,
            "submittedAt": row.submitted_at.isoformat() if row.submitted_at else None,
            "againstVersionNo": published.version_no if published else None,
            "changeCount": len(changes) if changes is not None else None,
            "changes": (changes or [])[:50],
            "isNew": published is None,
            "canApprove": can,
            "cannotApproveReason": why,
        })
    by_area: dict[str, int] = {}
    for item in items:
        by_area[item["area"]] = by_area.get(item["area"], 0) + 1
    return {"total": len(items), "byArea": by_area, "items": items}


def pending_count() -> dict[str, Any]:
    queue = pending_queue()
    return {"total": queue["total"], "canApprove": sum(1 for i in queue["items"] if i["canApprove"]),
            "byArea": queue["byArea"]}
