"""Coberturas do mercado angolano (PDF "Coberturas e Capitais", 1-Out-2026).

`Benefit`/`PlanBenefit` already exist in the schema (ART-012 V006). The
catalogue (`apps.product.domain.market_catalog`) follows the PDF: only the
3 coverages marked "B" in every column of its comparison matrix
(Hospitalização, Cirurgia de ambulatório, Urgências/ambulância) are `BASE` —
attached to every Plan automatically, never removable. Every other coverage
is `COMPLEMENTARY`; whether a given Plan includes it from the start ("B") or
merely offers it as optional ("O") is a Plan-level decision stored in
`PlanBenefit.configuration_json` (see `plan_configuration_service`).

`Benefit` is `TenantScopedModel` (ART-012 has no cross-tenant catalog
table), so the catalogue is seeded per-tenant, idempotently, the first time
it is needed — never assumed to already exist. The seed only ever *adds*:
it never overwrites a name/description/definition a tenant already edited.
"""
from __future__ import annotations

import uuid
from typing import Any

from django.db.models import Q

from apps.foundation.application.context import CurrentTenantProvider
from apps.product.domain.enums import BenefitStatus
from apps.product.domain.errors import InvalidBenefitSelectionError, MissingCoreBenefitsError
from apps.product.domain.market_catalog import BASE, CATALOG, CATALOG_BY_CODE, COMPLEMENTARY
from apps.product.infrastructure.models import Benefit, Plan, PlanBenefit

# Kept for callers/tests that only need code/name/category.
MARKET_CATALOG: list[dict[str, str]] = [
    {"code": e["code"], "name": e["name"], "benefit_type": e["benefit_type"]} for e in CATALOG
]


def ensure_market_catalog(tenant_id: uuid.UUID) -> None:
    """Idempotent. Creates any catalogue coverage the tenant is missing and
    back-fills an *empty* `definition_json`/`description` on rows that
    pre-date the library (never touches a non-empty one: a tenant may have
    edited it). Two queries in the steady state."""
    existing = {b.code: b for b in Benefit.objects.filter(code__in=list(CATALOG_BY_CODE))}
    missing = [e for e in CATALOG if e["code"] not in existing]
    if missing:
        Benefit.objects.bulk_create(
            [
                Benefit(
                    tenant_id=tenant_id,
                    code=e["code"],
                    name=e["name"],
                    benefit_type=e["benefit_type"],
                    description=e["description"],
                    definition_json=e["definition"],
                )
                for e in missing
            ]
        )
    for code, benefit in existing.items():
        entry = CATALOG_BY_CODE[code]
        updates: dict[str, Any] = {}
        if not benefit.definition_json:
            updates["definition_json"] = entry["definition"]
        if not benefit.description:
            updates["description"] = entry["description"]
        if updates:
            Benefit.objects.filter(id=benefit.id).update(**updates)


def list_benefits(
    *, category: str | None = None, status: str | None = BenefitStatus.ACTIVE.value, search: str | None = None
) -> Any:
    """`status=None`/`"ALL"` lists every status; the default (ACTIVE) keeps
    the original behaviour for callers that only offer selectable coverages."""
    tenant_id = CurrentTenantProvider.require().value
    ensure_market_catalog(tenant_id)
    queryset = Benefit.objects.all()
    if status and status != "ALL":
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(benefit_type=category)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("benefit_type", "code")


def attach_core_benefits(*, plan: Plan) -> None:
    """Called right after a Plan is created (product_service.create_plan)
    — the 3 BASE coverages are never something the caller opts into."""
    ensure_market_catalog(plan.tenant_id)
    core_benefits = Benefit.objects.filter(benefit_type=BASE)
    for benefit in core_benefits:
        PlanBenefit.objects.get_or_create(
            tenant_id=plan.tenant_id, plan=plan, benefit=benefit, defaults={"configuration_json": {"inclusion": "INCLUDED"}}
        )


def core_benefit_ids(tenant_id: uuid.UUID) -> set[uuid.UUID]:
    ensure_market_catalog(tenant_id)
    return set(Benefit.objects.filter(benefit_type=BASE).values_list("id", flat=True))


def resolve_complementary_benefits(*, tenant_id: uuid.UUID, benefit_ids: list[uuid.UUID]) -> list[Benefit]:
    """Validates a Plan-creation coverage selection (product_service.
    create_plan): every id must resolve to an ACTIVE COMPLEMENTARY Benefit
    of this tenant. BASE coverages are never selectable here — they are
    always attached automatically (attach_core_benefits), never opted
    into — so a caller passing a BASE id is treated the same as an
    unknown one: rejected."""
    if not benefit_ids:
        return []
    ensure_market_catalog(tenant_id)
    unique_ids = set(benefit_ids)
    benefits = list(
        Benefit.objects.filter(
            id__in=unique_ids, tenant_id=tenant_id, benefit_type=COMPLEMENTARY, status=BenefitStatus.ACTIVE.value
        )
    )
    if len(benefits) != len(unique_ids):
        found_ids = {b.id for b in benefits}
        missing = unique_ids - found_ids
        raise InvalidBenefitSelectionError(
            f"complementaryBenefitIds contains unknown, inactive or non-COMPLEMENTARY ids: {sorted(str(i) for i in missing)}"
        )
    return benefits


def list_plan_benefits(*, plan: Plan) -> Any:
    return PlanBenefit.objects.filter(plan=plan).select_related("benefit").order_by("benefit__benefit_type", "benefit__code")


def add_plan_benefit(*, plan: Plan, benefit: Benefit) -> PlanBenefit:
    plan_benefit, _ = PlanBenefit.objects.get_or_create(
        tenant_id=plan.tenant_id, plan=plan, benefit=benefit, defaults={"configuration_json": {"inclusion": "INCLUDED"}}
    )
    return plan_benefit


class CoreBenefitRemovalError(MissingCoreBenefitsError):
    """A caller tried to detach a BASE coverage from a Plan — never
    allowed, the 3 core coverages are mandatory for every Plan (Épico 1)."""


def remove_plan_benefit(*, plan: Plan, benefit: Benefit) -> None:
    if benefit.benefit_type == BASE:
        raise CoreBenefitRemovalError(
            f"Benefit '{benefit.code}' is a core (BASE) coverage and cannot be removed from a Plan"
        )
    PlanBenefit.objects.filter(plan=plan, benefit=benefit).delete()


def plan_has_all_core_benefits(*, plan: Plan) -> bool:
    ensure_market_catalog(plan.tenant_id)
    core_ids = set(Benefit.objects.filter(benefit_type=BASE).values_list("id", flat=True))
    attached_ids = set(PlanBenefit.objects.filter(plan=plan).values_list("benefit_id", flat=True))
    return core_ids.issubset(attached_ids)
