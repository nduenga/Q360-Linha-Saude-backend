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
