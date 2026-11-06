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
from apps.business_config.domain.scope import split_key
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.application.context import CurrentActorProvider


def _label(key: str, products: dict[str, str]) -> str:
    if is_product_setup_key(key):
        return f"Configuração do produto {products.get(product_id_of(key), product_id_of(key))}"
    base, product_id = split_key(key)
    entry = CATALOG_BY_KEY.get(base)
    label = entry["label"] if entry else base
    if product_id is not None:
        return f"{label} · produto {products.get(product_id, product_id)}"
    return label


def _can_approve(row: BusinessConfiguration, actor, rules: dict) -> tuple[bool, str | None]:
    actor_id = actor.actor_id if actor else None
    if row.created_by == actor_id and rules.get("four_eyes_required") is not False:
        return False, "Foi o utilizador atual que criou esta versão (aprovação por outra pessoa)."
    roles = {getattr(r, "value", r) for r in (actor.roles if actor else ())}
    allowed = set(rules.get("approval_roles") or [])
    if allowed and "ADMIN" not in roles and not roles & allowed:
        return False, f"O seu perfil não aprova configurações (perfis permitidos: {sorted(allowed | {'ADMIN'})})."
    return True, None


def eligible_approvers(row: BusinessConfiguration, rules: dict) -> list[dict[str, str]]:
    """Contas ativas que podem aprovar: sem isto, uma alteração fica parada sem
    que ninguém perceba porquê."""
    from apps.foundation.domain.permissions import Permission, Role, effective_role_permissions
    from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole

    configured = set(rules.get("approval_roles") or [])
    managers = {Permission.PRODUCT_MANAGE, Permission.PRICING_CONFIG_MANAGE}
    allowed = (configured | {Role.ADMIN.value}) if configured else {
        role.value for role, permissions in effective_role_permissions(row.tenant_id).items()
        if managers & set(permissions) and role is not Role.PLATFORM_ADMIN
    }
    account_ids = StaffAccountRole.objects.filter(role__in=allowed).values_list("staff_account_id", flat=True)
    excluded = {row.created_by} if rules.get("four_eyes_required") is not False else set()
    accounts = StaffAccount.objects.filter(id__in=account_ids, status=StaffAccount.ACTIVE).order_by("name")
    return [{"id": str(a.id), "name": a.name} for a in accounts if str(a.id) not in excluded]


def _impact(row: BusinessConfiguration) -> dict[str, int]:
    """Quantas cotações em curso e apólices a renovar esta alteração pode afetar."""
    import datetime

    from apps.policy.infrastructure.models import Policy
    from apps.quote.infrastructure.models import Quote

    product_id = product_id_of(row.config_key) if is_product_setup_key(row.config_key) else split_key(row.config_key)[1]
    quotes = Quote.objects.filter(status__in=("DRAFT", "READY", "IN_REVIEW", "APPROVED"))
    today = timezone.localdate()
    policies = Policy.objects.filter(status="ACTIVE", end_date__range=(today, today + datetime.timedelta(days=90)))
    if product_id:
        quotes = quotes.filter(plan__product_id=product_id)
        policies = policies.filter(plan__product_id=product_id)
    return {"quotesInProgress": quotes.count(), "policiesToRenew": policies.count()}


def pending_queue(*, area: str | None = None) -> dict[str, Any]:
    from apps.product.infrastructure.models import Product

    day = timezone.localdate()
    actor = CurrentActorProvider.get()
    rules = BusinessSnapshot.load().get("security.approval_rules") or {}
    pending = list(BusinessConfiguration.objects.filter(status="PENDING_APPROVAL").order_by("submitted_at", "created_at"))
    products = {str(p.id): p.name for p in Product.objects.filter(
        id__in=[product_id_of(r.config_key) if is_product_setup_key(r.config_key) else split_key(r.config_key)[1]
                for r in pending if is_product_setup_key(r.config_key) or split_key(r.config_key)[1]])}
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
        approvers = eligible_approvers(row, rules)
        items.append({
            "configurationId": str(row.id),
            "configKey": row.config_key,
            "label": _label(row.config_key, products),
            "area": row_area,
            "areaLabel": AREA_LABELS[row_area],
            "versionNo": row.version_no,
            "effectiveFrom": row.effective_from.isoformat() if row.effective_from else None,
            "createdBy": row.created_by,
            "createdByName": _staff_name(row.created_by),
            "submittedAt": row.submitted_at.isoformat() if row.submitted_at else None,
            "againstVersionNo": published.version_no if published else None,
            "changeCount": len(changes) if changes is not None else None,
            "changes": (changes or [])[:50],
            "isNew": published is None,
            "canApprove": can,
            "cannotApproveReason": why,
            "eligibleApprovers": approvers,
            "noEligibleApprover": not approvers,
            "approverAlert": None if approvers else "Falta um segundo aprovador elegível. Ative outra conta com este perfil para esta alteração poder avançar.",
            "impact": _impact(row),
        })
    by_area: dict[str, int] = {}
    for item in items:
        by_area[item["area"]] = by_area.get(item["area"], 0) + 1
    return {"total": len(items), "byArea": by_area, "items": items}


def _staff_name(actor_id: str | None) -> str | None:
    """Nome de quem propôs, para a fila não mostrar o identificador técnico."""
    import uuid as _uuid

    from apps.staff_accounts.infrastructure.models import StaffAccount

    try:
        key = _uuid.UUID(str(actor_id))
    except (TypeError, ValueError):
        return None
    return StaffAccount.objects.filter(id=key).values_list("name", flat=True).first()


def pending_count() -> dict[str, Any]:
    queue = pending_queue()
    return {"total": queue["total"], "canApprove": sum(1 for i in queue["items"] if i["canApprove"]),
            "byArea": queue["byArea"]}
