"""ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1 acceptance criteria: the 3
market-mandatory (BASE) coverages are always present on every Plan and can
never be removed; the 8 COMPLEMENTARY coverages are opt-in; a
ProductVersion cannot publish while a Plan is missing a BASE coverage.
"""
from __future__ import annotations

import pytest

from apps.product.application.benefit_service import MARKET_CATALOG


def _plan(client, *, product_code: str) -> dict:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    version = client.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}).data
    plan = client.post("/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC", "name": "Basic"}).data
    return {"productVersionId": version["id"], "planId": plan["id"]}


@pytest.mark.django_db
def test_benefit_catalog_has_all_11_market_coverages(admin_client):
    resp = admin_client.get("/api/v1/benefits?size=50")
    assert resp.status_code == 200
    codes = {item["code"] for item in resp.data["items"]}
    assert codes == {entry["code"] for entry in MARKET_CATALOG}


@pytest.mark.django_db
def test_benefit_catalog_filters_by_category(admin_client):
    resp = admin_client.get("/api/v1/benefits?category=BASE")
    assert resp.status_code == 200
    assert len(resp.data["items"]) == 3
    assert all(item["category"] == "BASE" for item in resp.data["items"])


@pytest.mark.django_db
def test_new_plan_automatically_gets_the_3_base_coverages(admin_client):
    refs = _plan(admin_client, product_code="BEN-PROD-1")
    resp = admin_client.get(f"/api/v1/plans/{refs['planId']}/benefits")
    assert resp.status_code == 200
    base_codes = {item["benefit"]["code"] for item in resp.data if item["benefit"]["category"] == "BASE"}
    assert base_codes == {"HOSPITALIZATION", "OUTPATIENT", "EMERGENCY"}


@pytest.mark.django_db
def test_complementary_coverage_can_be_added_and_removed(admin_client):
    refs = _plan(admin_client, product_code="BEN-PROD-2")
    pharmacy = next(
        item for item in admin_client.get("/api/v1/benefits?category=COMPLEMENTARY").data["items"]
        if item["code"] == "PHARMACY"
    )

    added = admin_client.post(
        f"/api/v1/plans/{refs['planId']}/benefits", {"benefitId": pharmacy["id"]}, format="json"
    )
    assert added.status_code == 201
    assert added.data["benefit"]["code"] == "PHARMACY"

    listed = admin_client.get(f"/api/v1/plans/{refs['planId']}/benefits").data
    assert any(item["benefit"]["code"] == "PHARMACY" for item in listed)

    removed = admin_client.delete(f"/api/v1/plans/{refs['planId']}/benefits/{pharmacy['id']}")
    assert removed.status_code == 204
    listed_after = admin_client.get(f"/api/v1/plans/{refs['planId']}/benefits").data
    assert not any(item["benefit"]["code"] == "PHARMACY" for item in listed_after)


@pytest.mark.django_db
def test_cannot_remove_a_base_coverage(admin_client):
    refs = _plan(admin_client, product_code="BEN-PROD-3")
    hospitalization = next(
        item for item in admin_client.get("/api/v1/benefits?category=BASE").data["items"]
        if item["code"] == "HOSPITALIZATION"
    )

    resp = admin_client.delete(f"/api/v1/plans/{refs['planId']}/benefits/{hospitalization['id']}")
    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION-400"

    listed = admin_client.get(f"/api/v1/plans/{refs['planId']}/benefits").data
    assert any(item["benefit"]["code"] == "HOSPITALIZATION" for item in listed)


@pytest.mark.django_db
def test_publish_succeeds_when_plan_has_all_base_coverages(admin_client):
    refs = _plan(admin_client, product_code="BEN-PROD-4")
    resp = admin_client.post(f"/api/v1/product-versions/{refs['productVersionId']}/publish")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_publish_fails_when_a_base_coverage_was_removed_via_direct_orm(admin_client, tenant):
    """Simulates data corruption/an old row predating this epic: a Plan
    missing a BASE coverage must never be allowed to publish."""
    from apps.product.infrastructure.models import PlanBenefit

    refs = _plan(admin_client, product_code="BEN-PROD-5")
    PlanBenefit.all_tenants.filter(plan_id=refs["planId"]).delete()

    resp = admin_client.post(f"/api/v1/product-versions/{refs['productVersionId']}/publish")
    assert resp.status_code == 400
    assert resp.data["code"] == "VALIDATION-400"
