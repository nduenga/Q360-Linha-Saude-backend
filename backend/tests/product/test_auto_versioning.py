"""ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 2: editing a product (any field,
even the most basic) rolls its version forward automatically — there is
no separate "create version" action anymore. Épico 3: every version is
open-ended (no `effectiveTo`)."""
from __future__ import annotations

import datetime

import pytest


def _product_with_plan_and_benefit(client, *, code: str) -> dict:
    product = client.post("/api/v1/products", {"code": code, "name": code}).data
    version = client.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}).data
    plan = client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC", "name": "Basic"}
    ).data
    complementary = next(
        item for item in client.get("/api/v1/benefits?category=COMPLEMENTARY").data["items"]
        if item["code"] == "DENTAL"
    )
    client.post(f"/api/v1/plans/{plan['id']}/benefits", {"benefitId": complementary["id"]}, format="json")
    # A Quote can only be created against a PUBLISHED version (OD-002,
    # ROADMAP_ANGOLA_CUSTOMIZATION.md) - publish AFTER the plan/benefit are
    # attached (both require a DRAFT version).
    client.post(f"/api/v1/product-versions/{version['id']}/publish")
    return {"product": product, "version": version, "plan": plan, "complementaryBenefitId": complementary["id"]}


@pytest.mark.django_db
def test_editing_product_retires_previous_version_and_publishes_next(admin_client):
    refs = _product_with_plan_and_benefit(admin_client, code="AUTOV-1")

    admin_client.put(
        f"/api/v1/products/{refs['product']['id']}", {"name": "AUTOV-1", "rowVersion": 0}
    )

    versions = admin_client.get(f"/api/v1/products/{refs['product']['id']}/versions").data["items"]
    assert len(versions) == 2
    old = next(v for v in versions if v["versionNo"] == 1)
    new = next(v for v in versions if v["versionNo"] == 2)
    assert old["status"] == "RETIRED"
    assert old["effectiveTo"] == datetime.date.today().isoformat()
    assert new["status"] == "PUBLISHED"
    assert new["effectiveTo"] is None
    assert new["effectiveFrom"] == datetime.date.today().isoformat()


@pytest.mark.django_db
def test_new_version_inherits_plans_and_their_benefits(admin_client):
    refs = _product_with_plan_and_benefit(admin_client, code="AUTOV-2")

    admin_client.put(
        f"/api/v1/products/{refs['product']['id']}", {"name": "AUTOV-2", "rowVersion": 0}
    )

    versions = admin_client.get(f"/api/v1/products/{refs['product']['id']}/versions").data["items"]
    new_version_id = next(v["id"] for v in versions if v["versionNo"] == 2)

    new_plans = admin_client.get(f"/api/v1/plans?productVersionId={new_version_id}").data["items"]
    assert len(new_plans) == 1
    new_plan = new_plans[0]
    assert new_plan["code"] == "BASIC"
    assert new_plan["id"] != refs["plan"]["id"]

    new_plan_benefits = admin_client.get(f"/api/v1/plans/{new_plan['id']}/benefits").data
    benefit_codes = {item["benefit"]["code"] for item in new_plan_benefits}
    assert benefit_codes == {"HOSPITALIZATION", "OUTPATIENT", "EMERGENCY", "DENTAL"}


@pytest.mark.django_db
def test_old_plan_and_quote_still_readable_after_version_retired(admin_client):
    """OD-ANGOLA-004: retiring a version must never break something that
    already references it."""
    refs = _product_with_plan_and_benefit(admin_client, code="AUTOV-3")
    proposer_id = admin_client.post(
        "/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "Holder"}
    ).data["id"]
    quote = admin_client.post(
        "/api/v1/quotes",
        {
            "productVersionId": refs["version"]["id"],
            "planId": refs["plan"]["id"],
            "proposerId": proposer_id,
            "effectiveDate": "2026-06-01",
        },
        format="json",
    ).data
    assert quote["productVersionId"] == refs["version"]["id"]

    admin_client.put(
        f"/api/v1/products/{refs['product']['id']}", {"name": "AUTOV-3", "rowVersion": 0}
    )

    still_there = admin_client.get(f"/api/v1/quotes/{quote['id']}")
    assert still_there.status_code == 200
    assert still_there.data["productVersionId"] == refs["version"]["id"]

    old_plan_still_readable = admin_client.get(f"/api/v1/plans/{refs['plan']['id']}")
    assert old_plan_still_readable.status_code == 200


@pytest.mark.django_db
def test_editing_a_product_with_no_version_yet_does_not_create_one(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "AUTOV-4", "name": "AUTOV-4"}).data
    admin_client.put(f"/api/v1/products/{product['id']}", {"name": "Renamed", "rowVersion": 0})

    versions = admin_client.get(f"/api/v1/products/{product['id']}/versions").data["items"]
    assert versions == []


@pytest.mark.django_db
def test_multiple_edits_increment_version_each_time(admin_client):
    refs = _product_with_plan_and_benefit(admin_client, code="AUTOV-5")
    admin_client.put(f"/api/v1/products/{refs['product']['id']}", {"name": "AUTOV-5", "rowVersion": 0})
    admin_client.put(f"/api/v1/products/{refs['product']['id']}", {"name": "AUTOV-5 v2", "rowVersion": 1})

    versions = admin_client.get(f"/api/v1/products/{refs['product']['id']}/versions").data["items"]
    version_numbers = sorted(v["versionNo"] for v in versions)
    assert version_numbers == [1, 2, 3]
    non_retired = [v for v in versions if v["status"] != "RETIRED"]
    assert len(non_retired) == 1
    assert non_retired[0]["versionNo"] == 3
