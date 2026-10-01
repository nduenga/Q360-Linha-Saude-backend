"""Q360-S2-02 acceptance criteria: "Benefício duplicado incompatível
bloqueado" (the benefit half has no ART-006 HTTP surface yet — see
OPEN_DECISIONS.md#S02-CONTRACT-001 — so only the plan half is exercised
via the API here).

DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26): ProductVersion
retired — a Plan belongs directly to a Product, and can be edited/deleted
at any time (no more DRAFT-only gating; what a Quote already contracted is
protected by its own content snapshot instead, see tests/quote/
test_quotes.py)."""
from __future__ import annotations

import pytest


def _product(client, *, code: str) -> dict:
    return client.post("/api/v1/products", {"code": code, "name": code}).data


@pytest.mark.django_db
def test_create_plan_under_product(admin_client):
    product = _product(admin_client, code="PLAN-1")
    response = admin_client.post(
        "/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic Plan"}
    )
    assert response.status_code == 201
    body = response.data
    assert set(body.keys()) == {"id", "productId", "code", "name", "description", "status", "settings", "rowVersion"}
    assert body["productId"] == product["id"]
    assert body["status"] == "ACTIVE"

    get_response = admin_client.get(f"/api/v1/plans/{body['id']}")
    assert get_response.status_code == 200


@pytest.mark.django_db
def test_duplicate_plan_code_within_product_is_conflict(admin_client):
    product = _product(admin_client, code="PLAN-2")
    admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "DUP", "name": "A"})
    response = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "DUP", "name": "B"})
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_list_plans_filtered_by_product(admin_client):
    product_a = _product(admin_client, code="PLAN-A")
    product_b = _product(admin_client, code="PLAN-B")
    admin_client.post("/api/v1/plans", {"productId": product_a["id"], "code": "A1", "name": "A1"})
    admin_client.post("/api/v1/plans", {"productId": product_b["id"], "code": "B1", "name": "B1"})

    response = admin_client.get(f"/api/v1/plans?productId={product_a['id']}")
    assert response.status_code == 200
    assert [item["code"] for item in response.data["items"]] == ["A1"]


def _complementary_benefit_id(client, code: str) -> str:
    items = client.get("/api/v1/benefits?category=COMPLEMENTARY").data["items"]
    return next(item["id"] for item in items if item["code"] == code)


@pytest.mark.django_db
def test_create_plan_with_complementary_coverages(admin_client):
    """Product Owner requirement (2026-09-24): a select of coverages at
    plan-creation time — no separate attach-per-coverage round trip
    needed."""
    product = _product(admin_client, code="PLAN-COV-1")
    dental_id = _complementary_benefit_id(admin_client, "DENTAL")
    optical_id = _complementary_benefit_id(admin_client, "OPTICAL")

    response = admin_client.post(
        "/api/v1/plans",
        {
            "productId": product["id"],
            "code": "PREMIUM",
            "name": "Premium",
            "complementaryBenefitIds": [dental_id, optical_id],
        },
        format="json",
    )
    assert response.status_code == 201

    attached = admin_client.get(f"/api/v1/plans/{response.data['id']}/benefits").data
    codes = {item["benefit"]["code"] for item in attached}
    # BASE coverages always auto-attached, plus the 2 chosen COMPLEMENTARY ones.
    assert codes == {"HOSPITALIZATION", "AMBULATORY_SURGERY", "EMERGENCY", "DENTAL", "OPTICAL"}


@pytest.mark.django_db
def test_second_basic_plan_in_same_product_is_conflict(admin_client):
    """Empty (or omitted) complementaryBenefitIds = a "basic" plan (BASE
    coverages only) - the Product Owner requirement is at most one of
    those per Product."""
    product = _product(admin_client, code="PLAN-COV-2")
    first = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC-1", "name": "Basic 1"})
    assert first.status_code == 201

    second = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC-2", "name": "Basic 2"})
    assert second.status_code == 409
    assert second.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_plan_with_identical_coverage_set_is_conflict(admin_client):
    product = _product(admin_client, code="PLAN-COV-3")
    dental_id = _complementary_benefit_id(admin_client, "DENTAL")

    first = admin_client.post(
        "/api/v1/plans",
        {"productId": product["id"], "code": "GOLD-1", "name": "Gold 1", "complementaryBenefitIds": [dental_id]},
        format="json",
    )
    assert first.status_code == 201

    # Same final coverage set (BASE + DENTAL) under a different code/name -
    # still rejected, because coverages (not the label) differentiate plans.
    second = admin_client.post(
        "/api/v1/plans",
        {"productId": product["id"], "code": "GOLD-2", "name": "Gold 2", "complementaryBenefitIds": [dental_id]},
        format="json",
    )
    assert second.status_code == 409
    assert second.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_different_coverage_sets_are_allowed(admin_client):
    product = _product(admin_client, code="PLAN-COV-4")
    dental_id = _complementary_benefit_id(admin_client, "DENTAL")
    optical_id = _complementary_benefit_id(admin_client, "OPTICAL")

    basic = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"})
    dental_only = admin_client.post(
        "/api/v1/plans",
        {"productId": product["id"], "code": "DENTAL-PLAN", "name": "Dental", "complementaryBenefitIds": [dental_id]},
        format="json",
    )
    dental_and_optical = admin_client.post(
        "/api/v1/plans",
        {
            "productId": product["id"],
            "code": "DENTAL-OPTICAL-PLAN",
            "name": "Dental+Optical",
            "complementaryBenefitIds": [dental_id, optical_id],
        },
        format="json",
    )
    assert basic.status_code == 201
    assert dental_only.status_code == 201
    assert dental_and_optical.status_code == 201


@pytest.mark.django_db
def test_selecting_a_base_benefit_as_complementary_is_rejected(admin_client):
    """BASE coverages are never opted into - they are always attached
    automatically. Passing one in `complementaryBenefitIds` is rejected,
    same as an unknown id."""
    product = _product(admin_client, code="PLAN-COV-5")
    hospitalization_id = next(
        item["id"] for item in admin_client.get("/api/v1/benefits?category=BASE").data["items"]
        if item["code"] == "HOSPITALIZATION"
    )

    response = admin_client.post(
        "/api/v1/plans",
        {
            "productId": product["id"],
            "code": "BAD",
            "name": "Bad",
            "complementaryBenefitIds": [hospitalization_id],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_edit_plan(admin_client):
    product = _product(admin_client, code="PLAN-EDIT-1")
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "EDIT", "name": "Original"}).data

    response = admin_client.patch(
        f"/api/v1/plans/{plan['id']}",
        {"name": "Renamed", "description": "now described", "rowVersion": plan["rowVersion"]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["name"] == "Renamed"
    assert response.data["description"] == "now described"
    assert response.data["rowVersion"] == plan["rowVersion"] + 1

    get_response = admin_client.get(f"/api/v1/plans/{plan['id']}")
    assert get_response.data["name"] == "Renamed"


@pytest.mark.django_db
def test_edit_plan_stale_row_version_is_version_conflict(admin_client):
    product = _product(admin_client, code="PLAN-EDIT-2")
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "STALE", "name": "Original"}).data

    response = admin_client.patch(
        f"/api/v1/plans/{plan['id']}",
        {"name": "Renamed", "rowVersion": plan["rowVersion"] + 1},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "VERSION-CONFLICT"


@pytest.mark.django_db
def test_delete_plan(admin_client):
    product = _product(admin_client, code="PLAN-DEL-1")
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "DEL", "name": "To delete"}).data

    response = admin_client.delete(f"/api/v1/plans/{plan['id']}")
    assert response.status_code == 204

    get_response = admin_client.get(f"/api/v1/plans/{plan['id']}")
    assert get_response.status_code == 404

    # A deleted Plan's coverages must not be left as orphaned rows blocking
    # a future Plan with the exact same coverage set from being created.
    recreated = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "DEL-2", "name": "Recreated"})
    assert recreated.status_code == 201


@pytest.mark.django_db
def test_cannot_delete_plan_once_a_quote_references_it(admin_client):
    """Same protection as delete_product: a plain (non-CASCADE) FK from
    `quote` to `plan` makes Postgres itself refuse the delete once a Quote
    exists against it; this surfaces as a clean 409, not a raw 500."""
    product = _product(admin_client, code="PLAN-DEL-2")
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "PUB", "name": "Original"}).data
    proposer = admin_client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": "123456789LA043",
            "email": "holder2@example.com",
            "phone": "+244900000001",
        },
    ).data
    admin_client.post(
        "/api/v1/quotes",
        {"planId": plan["id"], "proposerId": proposer["id"], "effectiveDate": "2026-06-01"},
        format="json",
    )

    response = admin_client.delete(f"/api/v1/plans/{plan['id']}")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"

    still_there = admin_client.get(f"/api/v1/plans/{plan['id']}")
    assert still_there.status_code == 200
