"""DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26) reformulation
of the old OD-002 ("once a product has a newer version, its earlier plans
can never start new business again"): without ProductVersion, the same
rule is expressed directly on the Plan — only an ACTIVE plan may be used
to create a new Quote; a Quote already created against a plan keeps
working after that plan goes INACTIVE (OD-ANGOLA-004's guarantee, now
carried by apps.quote.application.quote_service._plan_content_snapshot
instead of version immutability) — this rule only blocks *new* quotes."""
from __future__ import annotations

import pytest


def _proposer(client) -> str:
    return client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "dateOfBirth": "1985-04-12", "displayName": "Holder",
            "registrationNumber": "123456789LA042",
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data["id"]


@pytest.mark.django_db
def test_creating_a_quote_against_an_inactive_plan_is_rejected(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "OD002-INACTIVE", "name": "OD002-INACTIVE"}).data
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"}).data
    admin_client.patch(
        f"/api/v1/plans/{plan['id']}",
        {"name": plan["name"], "rowVersion": plan["rowVersion"]},
        format="json",
    )
    # Plans don't expose a status-only PATCH field; flip it directly to
    # exercise the create_quote guard without inventing an endpoint.
    from apps.product.infrastructure.models import Plan

    Plan.all_tenants.filter(id=plan["id"]).update(status="INACTIVE")

    response = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": _proposer(admin_client),
            "planId": plan["id"],
            "effectiveDate": "2026-06-01",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_a_quote_created_before_plan_goes_inactive_still_works_after(admin_client):
    """OD-ANGOLA-004: making a plan INACTIVE never breaks a Quote already
    created against it - only blocks the ability to start a *new* one."""
    from apps.product.infrastructure.models import Plan

    product = admin_client.post("/api/v1/products", {"code": "OD002-EXISTING", "name": "OD002-EXISTING"}).data
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"}).data

    quote = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": _proposer(admin_client),
            "planId": plan["id"],
            "effectiveDate": "2026-06-01",
        },
        format="json",
    ).data
    assert quote is not None and "id" in quote

    Plan.all_tenants.filter(id=plan["id"]).update(status="INACTIVE")

    fetched = admin_client.get(f"/api/v1/quotes/{quote['id']}")
    assert fetched.status_code == 200
    assert fetched.data["planId"] == plan["id"]
