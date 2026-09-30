"""Q360-S6-01..04 acceptance criteria: "Estado inicial válido • Proponente e
plano obrigatórios • ID único" (S6-01), "Membros elegíveis associados •
Alteração força repricing controlado" (S6-02), "Snapshot completo • Versões
guardadas • Recalculation cria novo run" (S6-03), "Validade segundo
parâmetro • Totais reconciliam" (S6-04)."""
from __future__ import annotations

import json

import pytest


def _plan(client, *, product_code: str) -> dict:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    plan = client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"}).data
    return {"productId": product["id"], "planId": plan["id"]}


def _parameter_set(client, *, code: str, base_premium: str = "100.00") -> None:
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": code,
            "effectiveFrom": "2026-01-01",
            "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": base_premium}],
        },
        format="json",
    ).data
    client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")


def _rating_table(client, *, code: str) -> None:
    created = client.post(
        "/api/v1/rating-tables",
        {
            "code": code,
            "name": code,
            "effectiveFrom": "2026-01-01",
            "currencyCode": "AOA",
            "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}],
        },
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")


def _proposer(client, *, registration_number: str = "123456789LA042", email: str = "holder@example.com") -> str:
    return client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": registration_number,
            "email": email,
            "phone": "+244900000000",
        },
    ).data["id"]


def _member(client, *, proposer_id: str, date_of_birth: str = "1990-01-01") -> str:
    return client.post(
        "/api/v1/members",
        {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": date_of_birth},
    ).data["id"]


def _quote_scope(client, *, code_suffix: str) -> dict:
    """Full working scope: product/plan + published rating table/parameter
    set (so pricing can actually succeed) + a proposer."""
    plan_ref = _plan(client, product_code=f"QUOTE-PROD-{code_suffix}")
    _parameter_set(client, code=f"QUOTE-PARAMS-{code_suffix}")
    _rating_table(client, code=f"QUOTE-TABLE-{code_suffix}")
    proposer_id = _proposer(client)
    return {**plan_ref, "proposerId": proposer_id}


@pytest.mark.django_db
def test_create_quote_starts_as_draft(admin_client):
    scope = _quote_scope(admin_client, code_suffix="1")
    response = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": scope["proposerId"],
            "planId": scope["planId"],
            "effectiveDate": "2026-06-01",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.data
    assert body["status"] == "DRAFT"
    assert body["rowVersion"] == 0
    assert body["latestPricingRunId"] is None
    # Validade por omissão (QUOTE_DEFAULT_VALIDITY_DAYS=30 em teste) foi calculada, não pedida ao cliente.
    assert body["validUntil"] == "2026-07-01"


@pytest.mark.django_db
def test_create_quote_unknown_references_is_validation_400(admin_client):
    import uuid

    response = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": str(uuid.uuid4()),
            "planId": str(uuid.uuid4()),
            "effectiveDate": "2026-06-01",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_add_eligible_member_is_included(admin_client):
    scope = _quote_scope(admin_client, code_suffix="2")
    quote = admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    member_id = _member(admin_client, proposer_id=scope["proposerId"])

    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    assert response.status_code == 200

    members = admin_client.get(f"/api/v1/quotes/{quote['id']}/members").data["items"]
    assert len(members) == 1
    # No eligibility RuleVersion published for this tenant -> CONFIG_ERROR -> EXCLUDED (fail-closed).
    assert members[0]["status"] == "EXCLUDED"


@pytest.mark.django_db
def test_add_member_from_another_proposer_is_validation_error(admin_client):
    scope = _quote_scope(admin_client, code_suffix="member-proposer-match")
    quote = admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    other_proposer_id = _proposer(
        admin_client, registration_number="123456789LA043", email="other-holder@example.com"
    )
    other_member_id = _member(admin_client, proposer_id=other_proposer_id)

    response = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/members", {"memberId": other_member_id}, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"
    assert admin_client.get(f"/api/v1/quotes/{quote['id']}/members").data["items"] == []
    
    
@pytest.mark.django_db
def test_add_inactive_member_is_validation_error(admin_client):
    from apps.client.infrastructure.models import InsuredMember

    scope = _quote_scope(admin_client, code_suffix="inactive-member")
    quote = admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    member_id = _member(admin_client, proposer_id=scope["proposerId"])
    InsuredMember.all_tenants.filter(id=member_id).update(status="INACTIVE")

    response = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"
    assert admin_client.get(f"/api/v1/quotes/{quote['id']}/members").data["items"] == []


@pytest.mark.django_db
def test_add_duplicate_member_is_conflict(admin_client):
    scope = _quote_scope(admin_client, code_suffix="3")
    quote = admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    member_id = _member(admin_client, proposer_id=scope["proposerId"])
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")

    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_price_quote_promotes_to_ready_and_creates_snapshot(admin_client):
    scope = _quote_scope(admin_client, code_suffix="4")
    quote = admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    member_id = _member(admin_client, proposer_id=scope["proposerId"])

    # Publish an ELIGIBILITY rule with no thresholds so members resolve to
    # ELIGIBLE (config present -> not CONFIG_ERROR) instead of EXCLUDED.
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": f"ELIG-{quote['id']}",
            "name": "Eligibility",
            "ruleDomain": "ELIGIBILITY",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": json.dumps({}),
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")

    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")

    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert response.status_code == 200
    assert response.data["status"] == "CALCULATED"
    first_run_id = response.data["pricingRunId"]

    refreshed = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    assert refreshed["status"] == "READY"
    assert refreshed["latestPricingRunId"] == first_run_id

    # recalculate=False with an existing CALCULATED run reuses it (no new run).
    again = admin_client.post(f"/api/v1/quotes/{quote['id']}/price", {"recalculate": False}, format="json")
    assert again.data["pricingRunId"] == first_run_id

    # recalculate=True always creates a new run (S6-03: "Recalculation cria novo run").
    recalculated = admin_client.post(f"/api/v1/quotes/{quote['id']}/price", {"recalculate": True}, format="json")
    assert recalculated.data["pricingRunId"] != first_run_id


@pytest.mark.django_db
def test_editing_ready_quote_demotes_to_draft(admin_client):
    scope = _quote_scope(admin_client, code_suffix="5")
    quote = admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    member_id = _member(admin_client, proposer_id=scope["proposerId"])
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": f"ELIG-{quote['id']}",
            "name": "Eligibility",
            "ruleDomain": "ELIGIBILITY",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": json.dumps({}),
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    admin_client.post(f"/api/v1/quotes/{quote['id']}/price")

    ready = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    assert ready["status"] == "READY"

    # QT-002: editing effectiveDate on a READY quote demotes it back to DRAFT
    # and invalidates the pricing reference.
    edited = admin_client.put(
        f"/api/v1/quotes/{quote['id']}",
        {"effectiveDate": "2026-07-01", "rowVersion": ready["rowVersion"]},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.data["status"] == "DRAFT"
    assert edited.data["latestPricingRunId"] is None


@pytest.mark.django_db
def test_update_quote_stale_row_version_is_version_conflict(admin_client):
    scope = _quote_scope(admin_client, code_suffix="6")
    quote = admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    ).data

    response = admin_client.put(
        f"/api/v1/quotes/{quote['id']}", {"effectiveDate": "2026-07-01", "rowVersion": 99}, format="json"
    )
    assert response.status_code == 409
    assert response.data["code"] == "VERSION-CONFLICT"


@pytest.mark.django_db
def test_price_quote_without_published_config_is_pricing_config_error(admin_client):
    plan_ref = _plan(admin_client, product_code="QUOTE-PROD-7")
    proposer_id = _proposer(admin_client)
    quote = admin_client.post(
        "/api/v1/quotes",
        {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    member_id = _member(admin_client, proposer_id=proposer_id)
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")

    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert response.status_code == 422
    assert response.data["code"] == "PRICING-CONFIG"


@pytest.mark.django_db
def test_list_quotes_filters_by_status(admin_client):
    scope = _quote_scope(admin_client, code_suffix="8")
    admin_client.post(
        "/api/v1/quotes",
        {**{k: scope[k] for k in ("proposerId", "planId")}, "effectiveDate": "2026-06-01"},
        format="json",
    )
    response = admin_client.get("/api/v1/quotes?status=DRAFT")
    assert response.status_code == 200
    assert response.data["page"]["totalElements"] >= 1
    assert all(item["status"] == "DRAFT" for item in response.data["items"])
