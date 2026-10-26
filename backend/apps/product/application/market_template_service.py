"""Carrega os modelos de produto/plano do PDF "Coberturas e Capitais"
(`apps.product.domain.market_templates`) para o tenant atual.

Idempotente: um produto/plano que já existe (mesmo código) nunca é tocado —
o GTE pode ter editado capitais e participação, e isso não se sobrepõe. Cada
plano novo passa pelas mesmas validações de qualquer plano criado à mão.
"""
from __future__ import annotations

from typing import Any

from apps.foundation.application.context import CurrentTenantProvider
from apps.product.application import product_service
from apps.product.application.benefit_service import ensure_market_catalog
from apps.product.application.plan_configuration_service import configure_plan_benefit, validate_plan
from apps.product.domain.market_templates import build_templates
from apps.product.infrastructure.models import Benefit, Plan, Product


def apply_market_templates(*, only_products: set[str] | None = None) -> dict[str, Any]:
    tenant_id = CurrentTenantProvider.require().value
    ensure_market_catalog(tenant_id)
    benefits = {b.code: b for b in Benefit.objects.all()}

    created_products: list[str] = []
    created_plans: list[str] = []
    skipped_plans: list[str] = []
    plan_reports: list[dict[str, Any]] = []

    for product_tpl in build_templates():
        if only_products and product_tpl["code"] not in only_products:
            continue
        product = Product.objects.filter(code=product_tpl["code"]).first()
        if product is None:
            product = product_service.create_product(
                code=product_tpl["code"], name=product_tpl["name"], description=product_tpl["description"]
            )
            created_products.append(product.code)

        for plan_tpl in product_tpl["plans"]:
            if Plan.objects.filter(product=product, code=plan_tpl["code"]).exists():
                skipped_plans.append(plan_tpl["code"])
                continue
            complementary_ids = [
                benefits[c["code"]].id
                for c in plan_tpl["coverages"]
                if benefits[c["code"]].benefit_type == "COMPLEMENTARY"
            ]
            plan = product_service.create_plan(
                product=product,
                code=plan_tpl["code"],
                name=plan_tpl["name"],
                description=plan_tpl["description"],
                complementary_benefit_ids=complementary_ids,
                settings=plan_tpl["settings"],
            )
            for coverage in plan_tpl["coverages"]:
                configure_plan_benefit(plan=plan, benefit=benefits[coverage["code"]], configuration=coverage["config"])
            created_plans.append(plan.code)
            report = validate_plan(plan=plan)
            plan_reports.append(
                {
                    "planCode": plan.code,
                    "valid": report["valid"],
                    "errors": report["errors"],
                    "warningCount": len(report["warnings"]),
                    "warnings": report["warnings"],
                }
            )

    return {
        "createdProducts": created_products,
        "createdPlans": created_plans,
        "skippedPlans": skipped_plans,
        "plans": plan_reports,
        "indicative": True,
    }
