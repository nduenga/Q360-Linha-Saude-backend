"""ROADMAP_APOLICES.md Fase 3 — issuance (signature) and activation
(first premium payment) through the real HTTP API, end to end from a
freshly-approved Quote."""
from __future__ import annotations

import datetime
import json

import pytest

from tests.policy.conftest import make_client


def _plan(client, *, product_code: str) -> dict:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    plan = client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"}).data
    return {"productId": product["id"], "planId": plan["id"]}


def _parameter_set(client, *, code: str) -> None:
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": code, "effectiveFrom": "2026-01-01", "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "1200.00"}]},
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


def _eligibility_rule(client, *, code: str, config: dict | None = None) -> None:
    created = client.post(
        "/api/v1/rule-versions",
        {"code": code, "name": code, "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps(config or {})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")


def _approver(tenant, *, actor_id: str = "approver-1"):
    return make_client(
        tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope="q360.read q360.write q360.approve", actor_id=actor_id
    )


def _nif_for_suffix(suffix: str) -> str:
    """Generate a structurally valid, deterministic singular NIF for a test."""
    numeric_part = sum((index + 1) * ord(char) for index, char in enumerate(suffix))
    return f"{numeric_part:09d}LA042"


def _approved_quote(admin_client, tenant, *, suffix: str, min_entry_age: int | None = None) -> dict:
    """Full setup: product/plan + published pricing config + eligibility
    rule + 1 titular member, priced, submitted and APPROVED."""
    plan_ref = _plan(admin_client, product_code=f"POL-ISS-{suffix}")
    _parameter_set(admin_client, code=f"POL-PARAMS-{suffix}")
    _rating_table(admin_client, code=f"POL-TABLE-{suffix}")
    config = {"minEntryAge": min_entry_age} if min_entry_age is not None else {}
    _eligibility_rule(admin_client, code=f"POL-ELIG-{suffix}", config=config)

    proposer_id = admin_client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": _nif_for_suffix(suffix),
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data["id"]
    member_id = admin_client.post(
        "/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data["id"]
    quote = admin_client.post(
        "/api/v1/quotes",
        {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    ready = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    submitted = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": ready["rowVersion"]}, format="json"
    ).data
    approved = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    ).data
    return {**approved, "memberId": member_id, "proposerId": proposer_id}


_SIGN_BODY = {
    "signatoryName": "Holder",
    "signatoryDocumentType": "BI",
    "signatoryDocumentNumber": "000000000BI000",
    "signatoryCapacity": "TOMADOR",
    "termMonths": 12,
    "paymentFrequency": "ANUAL",
}


@pytest.mark.django_db
def test_issue_policy_from_approved_quote(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="1")
    response = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    )
    assert response.status_code == 201, response.data
    policy = response.data
    assert policy["status"] == "PENDING_FIRST_PREMIUM"
    assert policy["startDate"] is None and policy["endDate"] is None
    assert policy["policyNumber"].startswith("APO-")
    assert policy["policyType"] == "INDIVIDUAL"

    # The Quote is now BOUND, not APPROVED — never issuable twice.
    refreshed_quote = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    assert refreshed_quote["status"] == "BOUND"

    members = admin_client.get(f"/api/v1/policies/{policy['id']}/members").data
    assert len(members) == 1
    assert members[0]["status"] == "ACTIVE"
    assert members[0]["inclusionDate"] is None  # not yet activated

    installments = admin_client.get(f"/api/v1/policies/{policy['id']}/installments").data
    assert len(installments) == 1
    assert installments[0]["status"] == "DUE"
    assert installments[0]["amount"] == "1200.00"


@pytest.mark.django_db
def test_cannot_issue_policy_twice_for_the_same_quote(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="2")
    approver = _approver(tenant)
    first = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    )
    assert first.status_code == 201

    second = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    )
    # The Quote is BOUND now, not APPROVED -> POLICY-STATE (409), never a
    # duplicate Policy.
    assert second.status_code == 409
    assert second.data["code"] == "POLICY-STATE"


@pytest.mark.django_db
def test_hard_stop_member_is_not_copied_onto_the_policy(admin_client, tenant):
    """A member excluded at subscription (HARD_STOP) never appears on the
    Policy at all — only eligible members are copied (PO-APO-2).

    Injected directly via the ORM after approval (not through
    `POST /quotes/{id}/members`): a HARD_STOP member makes
    `quote_service.price_quote` refuse to promote the Quote past DRAFT at
    all (`has_blocking_member`), so there is no real HTTP path to an
    APPROVED quote that already carries one — this proves issue_policy's
    own mapping is correct regardless of how such a row could exist."""
    quote = _approved_quote(admin_client, tenant, suffix="3")
    from apps.client.infrastructure.models import InsuredMember
    from apps.eligibility.infrastructure.models import EligibilityEvaluation
    from apps.quote.infrastructure.models import Quote, QuoteMember

    quote_obj = Quote.all_tenants.get(id=quote["id"])
    excluded_member = InsuredMember.all_tenants.create(
        tenant_id=tenant.id,
        proposer_id=quote["proposerId"],
        relationship_code="FILHO",
        first_name="Excluded",
        last_name="Child",
        date_of_birth=datetime.date(2020, 1, 1),
    )
    evaluation = EligibilityEvaluation.all_tenants.create(
        tenant_id=tenant.id,
        member_id=excluded_member.id,
        plan_id=quote_obj.plan_id,
        decision="HARD_STOP",
        input_snapshot_json={},
        evidence_json=[{"code": "ELIG-AGE-MIN", "severity": "ERROR", "message": "Below minimum age"}],
    )
    QuoteMember.all_tenants.create(
        tenant_id=tenant.id, quote=quote_obj, member=excluded_member, status="EXCLUDED", eligibility_evaluation=evaluation
    )

    response = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    )
    assert response.status_code == 201, response.data
    members = admin_client.get(f"/api/v1/policies/{response.data['id']}/members").data
    assert len(members) == 1  # only the original, eligible titular — never the HARD_STOP child
    assert members[0]["memberId"] == quote["memberId"]


@pytest.mark.django_db
def test_requested_start_date_before_signature_is_rejected(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="4")
    response = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {
            **_SIGN_BODY,
            "signedAt": "2026-06-10T14:00:00Z",
            "requestedStartDate": "2026-06-10",
            "rowVersion": quote["rowVersion"],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_activation_starts_risk_the_day_after_signature_and_payment(admin_client, tenant):
    """Signed 2026-06-10 14:00, paid 2026-06-13 -> risk starts 2026-06-14
    (day after the *later* of the two — ROADMAP_APOLICES.md "Início do
    risco"), never the same day as either."""
    quote = _approved_quote(admin_client, tenant, suffix="5")
    approver = _approver(tenant)
    policy = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    ).data

    response = approver.post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": "2026-06-13T09:00:00Z", "paymentReference": "REC-001", "rowVersion": policy["rowVersion"]},
        format="json",
    )
    assert response.status_code == 200, response.data
    activated = response.data
    assert activated["status"] == "ACTIVE"
    assert activated["startDate"] == "2026-06-14"
    assert activated["endDate"] == "2027-06-13"

    members = admin_client.get(f"/api/v1/policies/{policy['id']}/members").data
    assert members[0]["inclusionDate"] == "2026-06-14"

    installments = admin_client.get(f"/api/v1/policies/{policy['id']}/installments").data
    assert len(installments) == 1  # ANUAL -> only ever 1
    assert installments[0]["status"] == "PAID"
    assert installments[0]["paymentReference"] == "REC-001"


@pytest.mark.django_db
def test_activation_when_paid_same_day_as_signature_still_starts_next_day(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="6")
    approver = _approver(tenant)
    policy = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    ).data

    response = approver.post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": "2026-06-10T16:00:00Z", "rowVersion": policy["rowVersion"]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["startDate"] == "2026-06-11"


@pytest.mark.django_db
def test_monthly_frequency_creates_12_installments(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="7")
    approver = _approver(tenant)
    policy = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {
            "signatoryName": "Holder",
            "signatoryDocumentType": "BI",
            "signatoryDocumentNumber": "000000000BI000",
            "signatoryCapacity": "TOMADOR",
            "termMonths": 12,
            "paymentFrequency": "MENSAL",
            "signedAt": "2026-06-10T14:00:00Z",
            "rowVersion": quote["rowVersion"],
        },
        format="json",
    ).data

    approver.post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": "2026-06-10T16:00:00Z", "rowVersion": policy["rowVersion"]},
        format="json",
    )

    installments = admin_client.get(f"/api/v1/policies/{policy['id']}/installments").data
    assert len(installments) == 12
    assert [i["installmentNo"] for i in installments] == list(range(1, 13))
    assert installments[0]["status"] == "PAID"
    assert all(i["status"] == "DUE" for i in installments[1:])
    total = sum(float(i["amount"]) for i in installments)
    assert round(total, 2) == 1200.00


@pytest.mark.django_db
def test_only_an_approved_quote_can_be_signed(admin_client, tenant):
    plan_ref = _plan(admin_client, product_code="POL-DRAFT")
    proposer_id = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "H", "registrationNumber": "999999999LA999",
         "email": "h@example.com", "phone": "+244900000000"},
    ).data["id"]
    draft_quote = admin_client.post(
        "/api/v1/quotes", {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"}, format="json"
    ).data

    response = _approver(tenant).post(
        f"/api/v1/quotes/{draft_quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": draft_quote["rowVersion"]},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "POLICY-STATE"


@pytest.mark.django_db
def test_lookup_by_policy_number(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="8")
    policy = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    ).data

    found = admin_client.get(f"/api/v1/policies?policyNumber={policy['policyNumber']}").data
    assert len(found["items"]) == 1
    assert found["items"][0]["id"] == policy["id"]
