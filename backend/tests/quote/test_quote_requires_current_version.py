"""ROADMAP_ANGOLA_CUSTOMIZATION.md OD-002: once a product has a newer
version, its earlier plans can never start new business again - only the
current PUBLISHED version may be used to create a new Quote. A Quote
already created against a version that is later retired keeps working
(OD-ANGOLA-004, proven in tests/product/test_auto_versioning.py) - this
rule only blocks *new* quotes."""
from __future__ import annotations

import pytest


def _proposer(client) -> str:
    return client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": "123456789LA042",
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data["id"]


@pytest.mark.django_db
def test_creating_a_quote_against_a_draft_version_is_rejected(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "OD002-DRAFT", "name": "OD002-DRAFT"}).data
    version = admin_client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    ).data
    plan = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC", "name": "Basic"}
    ).data
    # Never published - stays DRAFT.

    response = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": _proposer(admin_client),
            "productVersionId": version["id"],
            "planId": plan["id"],
            "effectiveDate": "2026-06-01",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_creating_a_quote_against_a_retired_version_is_rejected(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "OD002-RETIRED", "name": "OD002-RETIRED"}).data
    old_version = admin_client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    ).data
    old_plan = admin_client.post(
        "/api/v1/plans", {"productVersionId": old_version["id"], "code": "BASIC", "name": "Basic"}
    ).data
    admin_client.post(f"/api/v1/product-versions/{old_version['id']}/publish")

    # Any edit to the product auto-retires old_version and publishes a new one.
    admin_client.put(f"/api/v1/products/{product['id']}", {"name": "Renamed", "rowVersion": 0}, format="json")

    response = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": _proposer(admin_client),
            "productVersionId": old_version["id"],
            "planId": old_plan["id"],
            "effectiveDate": "2026-06-01",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_a_quote_created_before_retirement_still_works_after(admin_client):
    """OD-ANGOLA-004: retiring a version never breaks a Quote already
    created against it - only blocks the ability to start a *new* one."""
    product = admin_client.post("/api/v1/products", {"code": "OD002-EXISTING", "name": "OD002-EXISTING"}).data
    version = admin_client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    ).data
    plan = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC", "name": "Basic"}
    ).data
    admin_client.post(f"/api/v1/product-versions/{version['id']}/publish")

    quote = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": _proposer(admin_client),
            "productVersionId": version["id"],
            "planId": plan["id"],
            "effectiveDate": "2026-06-01",
        },
        format="json",
    ).data
    assert quote is not None and "id" in quote

    # Product edited afterwards -> version retired, new one published.
    admin_client.put(f"/api/v1/products/{product['id']}", {"name": "Renamed Again", "rowVersion": 0}, format="json")

    fetched = admin_client.get(f"/api/v1/quotes/{quote['id']}")
    assert fetched.status_code == 200
    assert fetched.data["productVersionId"] == version["id"]
