"""ROADMAP_APOLICES.md Fase 4 — coverage verification through the real
HTTP API, built on top of an activated Policy (Fase 3 flow)."""
from __future__ import annotations

import datetime
import json

import pytest

from tests.policy.test_issuance import _SIGN_BODY, _approved_quote, _approver


def _activate(admin_client, tenant, *, suffix: str, signed_at: str = "2026-06-10T14:00:00Z", paid_at: str = "2026-06-10T16:00:00Z") -> dict:
    quote = _approved_quote(admin_client, tenant, suffix=suffix)
    approver = _approver(tenant)
    policy = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": signed_at, "rowVersion": quote["rowVersion"]},
        format="json",
    ).data
    activated = approver.post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": paid_at, "rowVersion": policy["rowVersion"]},
        format="json",
    ).data
    return {**activated, "memberId": quote["memberId"]}


@pytest.mark.django_db
def test_coverage_before_activation_is_awaiting_first_premium(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="1")
    policy = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]},
        format="json",
    ).data

    response = admin_client.get(f"/api/v1/policies/{policy['id']}/coverage?memberId={quote['memberId']}")
    assert response.status_code == 200
    assert response.data["covered"] is False
    assert response.data["reasonCode"] == "POLICY_AWAITING_FIRST_PREMIUM"


@pytest.mark.django_db
def test_covered_on_start_date_for_a_base_benefit(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="2")
    response = admin_client.get(
        f"/api/v1/policies/{policy['id']}/coverage?memberId={policy['memberId']}"
        f"&date={policy['startDate']}&benefitCategory=HOSPITALIZATION"
    )
    assert response.status_code == 200, response.data
    assert response.data["covered"] is True
    assert response.data["reasonCode"] == "COVERED"


@pytest.mark.django_db
def test_not_covered_the_day_before_start_date(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="3")
    day_before = (datetime.date.fromisoformat(policy["startDate"]) - datetime.timedelta(days=1)).isoformat()
    response = admin_client.get(f"/api/v1/policies/{policy['id']}/coverage?memberId={policy['memberId']}&date={day_before}")
    assert response.data["covered"] is False
    assert response.data["reasonCode"] == "POLICY_NOT_IN_FORCE"


@pytest.mark.django_db
def test_benefit_not_contracted(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="4")
    response = admin_client.get(
        f"/api/v1/policies/{policy['id']}/coverage?memberId={policy['memberId']}"
        f"&date={policy['startDate']}&benefitCategory=DENTAL"
    )
    assert response.data["covered"] is False
    assert response.data["reasonCode"] == "BENEFIT_NOT_IN_PLAN"


@pytest.mark.django_db
def test_lookup_by_policy_number(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="5")
    response = admin_client.get(
        f"/api/v1/coverage?policyNumber={policy['policyNumber']}&memberId={policy['memberId']}&date={policy['startDate']}"
    )
    assert response.status_code == 200
    assert response.data["covered"] is True
    assert response.data["policyNumber"] == policy["policyNumber"]


@pytest.mark.django_db
def test_no_member_id_checks_every_member(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="6")
    response = admin_client.get(f"/api/v1/policies/{policy['id']}/coverage?date={policy['startDate']}")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["memberId"] == policy["memberId"]
    assert response.data["results"][0]["covered"] is True


@pytest.mark.django_db
def test_waiting_period_for_maternity(admin_client, tenant):
    """A dedicated setup (not `_approved_quote`): a MATERNITY-complementary
    plan, an eligibility rule with `waitingPeriod.defaultDaysByBenefitCategory`,
    and a policy activated on a known date — proves the waiting period
    computed at activation (Fase 3, `_waiting_period_ends`) actually gates
    coverage here."""
    product = admin_client.post("/api/v1/products", {"code": "COV-WP", "name": "COV-WP"}).data
    maternity_id = next(
        item["id"] for item in admin_client.get("/api/v1/benefits?category=COMPLEMENTARY").data["items"]
        if item["code"] == "MATERNITY"
    )
    plan = admin_client.post(
        "/api/v1/plans",
        {"productId": product["id"], "code": "MAT", "name": "Maternity", "complementaryBenefitIds": [maternity_id]},
        format="json",
    ).data
    params = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "COV-WP-PARAMS", "effectiveFrom": "2026-01-01", "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "1200.00"}]},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{params['id']}/publish")
    table = admin_client.post(
        "/api/v1/rating-tables",
        {"code": "COV-WP-TABLE", "name": "t", "effectiveFrom": "2026-01-01", "currencyCode": "AOA", "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}]},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rating-table/{table['id']}/publish")
    elig_rule = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": "COV-WP-ELIG", "name": "e", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": json.dumps({"waitingPeriod": {"defaultDaysByBenefitCategory": {"MATERNITY": 300}}}),
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{elig_rule['id']}/publish")

    proposer_id = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "H", "registrationNumber": "222222222LA042", "email": "h@example.com", "phone": "+244900000000"},
    ).data["id"]
    member_id = admin_client.post(
        "/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data["id"]
    quote = admin_client.post(
        "/api/v1/quotes", {"planId": plan["id"], "proposerId": proposer_id, "effectiveDate": "2026-06-01"}, format="json"
    ).data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    ready = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    submitted = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": ready["rowVersion"]}, format="json").data
    approver = _approver(tenant)
    approved = approver.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    ).data
    policy = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": approved["rowVersion"]},
        format="json",
    ).data
    activated = approver.post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": "2026-06-10T16:00:00Z", "rowVersion": policy["rowVersion"]},
        format="json",
    ).data
    # start_date = 2026-06-11; waiting period ends 300 days later.
    assert activated["startDate"] == "2026-06-11"

    still_waiting = admin_client.get(
        f"/api/v1/policies/{policy['id']}/coverage?memberId={member_id}&date=2026-07-01&benefitCategory=MATERNITY"
    )
    assert still_waiting.data["covered"] is False
    assert still_waiting.data["reasonCode"] == "IN_WAITING_PERIOD"
    assert still_waiting.data["waitingPeriodEnds"] == "2027-04-07"  # 2026-06-11 + 300 days

    after_waiting = admin_client.get(
        f"/api/v1/policies/{policy['id']}/coverage?memberId={member_id}&date=2027-05-01&benefitCategory=MATERNITY"
    )
    assert after_waiting.data["covered"] is True
