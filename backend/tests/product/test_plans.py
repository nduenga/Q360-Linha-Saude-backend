"""Q360-S2-02 acceptance criteria: "Plano pertence a uma versão • Benefício
duplicado incompatível bloqueado" (the benefit half has no ART-006 HTTP
surface yet — see OPEN_DECISIONS.md#S02-CONTRACT-001 — so only the
plan/version half is exercised via the API here)."""
from __future__ import annotations

import pytest


def _draft_version(client, *, product_code: str) -> tuple[dict, dict]:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    version = client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    ).data
    return product, version


@pytest.mark.django_db
def test_create_plan_under_draft_version(admin_client):
    _, version = _draft_version(admin_client, product_code="PLAN-1")
    response = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC", "name": "Basic Plan"}
    )
    assert response.status_code == 201
    body = response.data
    assert set(body.keys()) == {"id", "productVersionId", "code", "name", "description", "status", "rowVersion"}
    assert body["productVersionId"] == version["id"]
    assert body["status"] == "ACTIVE"

    get_response = admin_client.get(f"/api/v1/plans/{body['id']}")
    assert get_response.status_code == 200


@pytest.mark.django_db
def test_duplicate_plan_code_within_version_is_conflict(admin_client):
    _, version = _draft_version(admin_client, product_code="PLAN-2")
    admin_client.post("/api/v1/plans", {"productVersionId": version["id"], "code": "DUP", "name": "A"})
    response = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "DUP", "name": "B"}
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_cannot_add_plan_to_published_version(admin_client):
    _, version = _draft_version(admin_client, product_code="PLAN-3")
    admin_client.post(f"/api/v1/product-versions/{version['id']}/publish")

    response = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "TOO-LATE", "name": "Too late"}
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_list_plans_filtered_by_product_version(admin_client):
    _, version_a = _draft_version(admin_client, product_code="PLAN-A")
    _, version_b = _draft_version(admin_client, product_code="PLAN-B")
    admin_client.post("/api/v1/plans", {"productVersionId": version_a["id"], "code": "A1", "name": "A1"})
    admin_client.post("/api/v1/plans", {"productVersionId": version_b["id"], "code": "B1", "name": "B1"})

    response = admin_client.get(f"/api/v1/plans?productVersionId={version_a['id']}")
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
    _, version = _draft_version(admin_client, product_code="PLAN-COV-1")
    dental_id = _complementary_benefit_id(admin_client, "DENTAL")
    optical_id = _complementary_benefit_id(admin_client, "OPTICAL")

    response = admin_client.post(
        "/api/v1/plans",
        {
            "productVersionId": version["id"],
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
    assert codes == {"HOSPITALIZATION", "OUTPATIENT", "EMERGENCY", "DENTAL", "OPTICAL"}


@pytest.mark.django_db
def test_second_basic_plan_in_same_version_is_conflict(admin_client):
    """Empty (or omitted) complementaryBenefitIds = a "basic" plan (BASE
    coverages only) - the Product Owner requirement is at most one of
    those per ProductVersion."""
    _, version = _draft_version(admin_client, product_code="PLAN-COV-2")
    first = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC-1", "name": "Basic 1"}
    )
    assert first.status_code == 201

    second = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC-2", "name": "Basic 2"}
    )
    assert second.status_code == 409
    assert second.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_plan_with_identical_coverage_set_is_conflict(admin_client):
    _, version = _draft_version(admin_client, product_code="PLAN-COV-3")
    dental_id = _complementary_benefit_id(admin_client, "DENTAL")

    first = admin_client.post(
        "/api/v1/plans",
        {
            "productVersionId": version["id"],
            "code": "GOLD-1",
            "name": "Gold 1",
            "complementaryBenefitIds": [dental_id],
        },
        format="json",
    )
    assert first.status_code == 201

    # Same final coverage set (BASE + DENTAL) under a different code/name -
    # still rejected, because coverages (not the label) differentiate plans.
    second = admin_client.post(
        "/api/v1/plans",
        {
            "productVersionId": version["id"],
            "code": "GOLD-2",
            "name": "Gold 2",
            "complementaryBenefitIds": [dental_id],
        },
        format="json",
    )
    assert second.status_code == 409
    assert second.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_different_coverage_sets_are_allowed(admin_client):
    _, version = _draft_version(admin_client, product_code="PLAN-COV-4")
    dental_id = _complementary_benefit_id(admin_client, "DENTAL")
    optical_id = _complementary_benefit_id(admin_client, "OPTICAL")

    basic = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC", "name": "Basic"}
    )
    dental_only = admin_client.post(
        "/api/v1/plans",
        {"productVersionId": version["id"], "code": "DENTAL-PLAN", "name": "Dental", "complementaryBenefitIds": [dental_id]},
        format="json",
    )
    dental_and_optical = admin_client.post(
        "/api/v1/plans",
        {
            "productVersionId": version["id"],
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
    _, version = _draft_version(admin_client, product_code="PLAN-COV-5")
    hospitalization_id = next(
        item["id"] for item in admin_client.get("/api/v1/benefits?category=BASE").data["items"]
        if item["code"] == "HOSPITALIZATION"
    )

    response = admin_client.post(
        "/api/v1/plans",
        {
            "productVersionId": version["id"],
            "code": "BAD",
            "name": "Bad",
            "complementaryBenefitIds": [hospitalization_id],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"
