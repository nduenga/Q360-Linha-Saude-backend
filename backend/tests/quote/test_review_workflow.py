"""Q360-S7-01..03 acceptance criteria: "Só válida submete • Transição
determinística • Submitter não aprova" (S7-01); "Pode devolver para
correcção • Não altera snapshot" (S7-02); segregation of duties enforced
both in application code and by ART-012's `ck_quote_four_eyes`/
`ck_decision_four_eyes` CHECK constraints."""
from __future__ import annotations

import json

import pytest

from tests.quote.conftest import make_client


def _plan(client, *, product_code: str) -> dict:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    plan = client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"}).data
    return {"productId": product["id"], "planId": plan["id"]}


def _parameter_set(client, *, code: str) -> None:
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": code, "effectiveFrom": "2026-01-01", "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "100.00"}]},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")


def _rating_table(client, *, code: str) -> None:
    created = client.post(
        "/api/v1/rating-tables",
        {"code": code, "name": code, "effectiveFrom": "2026-01-01", "currencyCode": "AOA", "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}]},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")


def _eligibility_rule(client, *, code: str) -> None:
    created = client.post(
        "/api/v1/rule-versions",
        {"code": code, "name": code, "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01", "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")


def _ready_quote(client, *, code_suffix: str) -> dict:
    """Full setup ending with a READY quote (S6 already proven), so S7
    tests start from a real, priced quote rather than a bare fixture."""
    plan_ref = _plan(client, product_code=f"REVIEW-PROD-{code_suffix}")
    _parameter_set(client, code=f"REVIEW-PARAMS-{code_suffix}")
    _rating_table(client, code=f"REVIEW-TABLE-{code_suffix}")
    _eligibility_rule(client, code=f"REVIEW-ELIG-{code_suffix}")
    proposer_id = client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": "123456789LA042",
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data["id"]
    member_id = client.post(
        "/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data["id"]
    quote = client.post(
        "/api/v1/quotes",
        {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    client.post(f"/api/v1/quotes/{quote['id']}/price")
    return client.get(f"/api/v1/quotes/{quote['id']}").data


@pytest.mark.django_db
def test_submit_ready_quote_moves_to_in_review_and_creates_task(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="1")
    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json")
    assert response.status_code == 200
    assert response.data["status"] == "IN_REVIEW"

    review = admin_client.get(f"/api/v1/quotes/{quote['id']}/review")
    assert review.status_code == 200
    assert review.data["status"] == "OPEN"
    assert review.data["quoteId"] == quote["id"]


@pytest.mark.django_db
def test_submit_non_ready_quote_is_quote_state_error(admin_client):
    plan_ref = _plan(admin_client, product_code="REVIEW-PROD-2")
    proposer_id = admin_client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "H",
            "registrationNumber": "123456789LA042",
            "email": "h@example.com",
            "phone": "+244900000000",
        },
    ).data["id"]
    quote = admin_client.post(
        "/api/v1/quotes", {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"}, format="json"
    ).data
    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": 0}, format="json")
    assert response.status_code == 409
    assert response.data["code"] == "QUOTE-STATE"


@pytest.mark.django_db
def test_submitter_cannot_approve_own_quote(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="3")
    submitted = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json").data

    # Same actor ("actor-1", the default in admin_client) tries to approve
    # its own submission -> forbidden regardless of role/scope.
    response = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["code"] == "SEC-403"


@pytest.mark.django_db
def test_different_actor_can_approve(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="4")
    submitted = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json").data

    approver_client = make_client(tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope="q360.read q360.write q360.approve", actor_id="approver-1")
    response = approver_client.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "MEETS_CRITERIA", "rowVersion": submitted["rowVersion"]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "APPROVED"

    history = admin_client.get(f"/api/v1/quotes/{quote['id']}/history").data
    assert [h["toStatus"] for h in history] == ["DRAFT", "READY", "IN_REVIEW", "APPROVED"]


@pytest.mark.django_db
def test_reject_requires_reason_code(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="5")
    admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json")

    approver_client = make_client(tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope="q360.read q360.write q360.approve", actor_id="approver-2")
    missing_reason = approver_client.post(
        f"/api/v1/quotes/{quote['id']}/decision", {"decision": "REJECT", "rowVersion": 1}, format="json"
    )
    assert missing_reason.status_code == 400
    assert missing_reason.data["code"] == "VALIDATION-400"

    rejected = approver_client.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "REJECT", "reasonCode": "INCOMPLETE_DOCS", "rowVersion": 1},
        format="json",
    )
    assert rejected.status_code == 200
    assert rejected.data["status"] == "REJECTED"


@pytest.mark.django_db
def test_return_sends_quote_back_to_ready_and_task_returned(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="6")
    admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json")

    reviewer_client = make_client(tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope="q360.read q360.write q360.approve", actor_id="reviewer-1")
    response = reviewer_client.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "RETURN", "reasonCode": "NEEDS_MORE_INFO", "rowVersion": 1},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "READY"

    review = admin_client.get(f"/api/v1/quotes/{quote['id']}/review").data
    assert review["status"] == "RETURNED"


@pytest.mark.django_db
def test_decision_without_permission_is_forbidden(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="7")
    submitted = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json").data

    # Has the q360.approve scope but an actor without a role has no quote:approve permission.
    weak_client = make_client(tenant_id=tenant.id, roles=[], scope="q360.read q360.write q360.approve", actor_id="weak-1")
    response = weak_client.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["code"] == "AUTH-403"


@pytest.mark.django_db
def test_review_queue_lists_open_tasks(admin_client):
    quote = _ready_quote(admin_client, code_suffix="8")
    admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json")

    response = admin_client.get("/api/v1/reviews?status=OPEN")
    assert response.status_code == 200
    assert any(item["quoteId"] == quote["id"] for item in response.data["items"])


@pytest.mark.django_db
def test_forbidden_transition_decide_without_submit(admin_client):
    """ART-009 "Forbidden Transitions": DRAFT/READY -> APPROVED directly is
    not allowed; a quote must go through IN_REVIEW."""
    quote = _ready_quote(admin_client, code_suffix="9")
    response = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": quote["rowVersion"]},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "QUOTE-STATE"
