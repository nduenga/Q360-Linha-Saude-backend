"""Coberturas do mercado angolano (ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1).

`Benefit`/`PlanBenefit` already exist in the schema (ART-012 V006) with no
HTTP surface (OPEN_DECISIONS.md#S02-CONTRACT-001) — this module gives them
real behaviour: a fixed catalogue of the 11 coverages from the ARSEG-market
guide supplied by the Product Owner (3 BASE, always attached to every
Plan automatically; 8 COMPLEMENTARY, opt-in per Plan), and the invariant
that a ProductVersion cannot publish while any of its Plans is missing a
BASE coverage.

`Benefit` is `TenantScopedModel` (ART-012 has no cross-tenant catalog
table), so the fixed catalogue is seeded per-tenant, idempotently, the
first time it is needed — never assumed to already exist.
"""
from __future__ import annotations

import uuid
from typing import Any

from apps.foundation.application.context import CurrentTenantProvider
from apps.product.domain.enums import BenefitStatus
from apps.product.domain.errors import MissingCoreBenefitsError
from apps.product.infrastructure.models import Benefit, Plan, PlanBenefit

BASE = "BASE"
COMPLEMENTARY = "COMPLEMENTARY"

# ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1 — matriz ARSEG fornecida pelo
# Product Owner (2026-09-19). Os `code` são uma proposta técnica minha
# (OD-ANGOLA-007, ainda em aberto) — fáceis de renomear agora, caros depois
# de haver dados reais a referenciá-los.
_CORE_BENEFITS: list[dict[str, str]] = [
    {"code": "HOSPITALIZATION", "name": "Internamento Hospitalar e Cirurgia", "benefit_type": BASE},
    {"code": "OUTPATIENT", "name": "Ambulatório", "benefit_type": BASE},
    {"code": "EMERGENCY", "name": "Urgência Médica", "benefit_type": BASE},
]

_COMPLEMENTARY_BENEFITS: list[dict[str, str]] = [
    {"code": "PHARMACY", "name": "Medicamentos / Farmácia", "benefit_type": COMPLEMENTARY},
    {"code": "MATERNITY", "name": "Maternidade e Parto", "benefit_type": COMPLEMENTARY},
    {"code": "DENTAL", "name": "Estomatologia (Medicina Dentária)", "benefit_type": COMPLEMENTARY},
    {"code": "OPTICAL", "name": "Oftalmologia e Óptica", "benefit_type": COMPLEMENTARY},
    {"code": "PROSTHESIS", "name": "Próteses e Ortóteses", "benefit_type": COMPLEMENTARY},
    {"code": "PHYSIOTHERAPY", "name": "Fisioterapia e Reabilitação", "benefit_type": COMPLEMENTARY},
    {"code": "MEDICAL_EVACUATION", "name": "Evacuação Médica Internacional", "benefit_type": COMPLEMENTARY},
    {"code": "TRAVEL_ASSISTANCE", "name": "Assistência em Viagem", "benefit_type": COMPLEMENTARY},
]

MARKET_CATALOG: list[dict[str, str]] = [*_CORE_BENEFITS, *_COMPLEMENTARY_BENEFITS]


def ensure_market_catalog(tenant_id: uuid.UUID) -> None:
    """Idempotent: creates the 11 fixed coverages for a tenant if any are
    missing. Never touches a row that already exists (a tenant may have
    edited name/description; this must not clobber that)."""
    for entry in MARKET_CATALOG:
        Benefit.objects.get_or_create(
            tenant_id=tenant_id,
            code=entry["code"],
            defaults={"name": entry["name"], "benefit_type": entry["benefit_type"]},
        )


def list_benefits(*, category: str | None = None) -> Any:
    tenant_id = CurrentTenantProvider.require().value
    ensure_market_catalog(tenant_id)
    queryset = Benefit.objects.filter(status=BenefitStatus.ACTIVE.value).order_by("benefit_type", "code")
    if category:
        queryset = queryset.filter(benefit_type=category)
    return queryset


def attach_core_benefits(*, plan: Plan) -> None:
    """Called right after a Plan is created (product_service.create_plan)
    — the 3 BASE coverages are never something the caller opts into."""
    ensure_market_catalog(plan.tenant_id)
    core_benefits = Benefit.objects.filter(benefit_type=BASE)
    for benefit in core_benefits:
        PlanBenefit.objects.get_or_create(
            tenant_id=plan.tenant_id, plan=plan, benefit=benefit, defaults={"configuration_json": {}}
        )


def list_plan_benefits(*, plan: Plan) -> Any:
    return PlanBenefit.objects.filter(plan=plan).select_related("benefit").order_by("benefit__benefit_type", "benefit__code")


def add_plan_benefit(*, plan: Plan, benefit: Benefit) -> PlanBenefit:
    plan_benefit, _ = PlanBenefit.objects.get_or_create(
        tenant_id=plan.tenant_id, plan=plan, benefit=benefit, defaults={"configuration_json": {}}
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
