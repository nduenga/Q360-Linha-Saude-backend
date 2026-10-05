"""Integration tests for the Fase 1 self-service endpoints
(ROADMAP_PORTAL_CLIENTE.md), migrated to Policy in Fase 6
(DECISIONS_TAKEN.md#S09-POLICY-001) — GET /me, GET /coverage,
GET /plan-benefits, POST /eligibility. Same django_db style as
test_portal_auth_api.py.
"""
from __future__ import annotations

import datetime

import pytest
from django.core import mail
from rest_framework.test import APIClient

_EMAIL = "cliente@example.com"
_START_DATE = datetime.date(2026, 6, 2)
_END_DATE = datetime.date(2027, 6, 1)


def _setup_active_policy_with_member(admin_client, tenant, *, policy_number: str, registration_number: str) -> dict:
    proposer = admin_client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Cliente Teste",
            "registrationNumber": registration_number,
            "email": _EMAIL,
            "phone": "+244900000000",
        },
    ).data
    product = admin_client.post("/api/v1/products", {"code": f"PORTAL-{policy_number}", "name": "Portal Product"}).data
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "PLAN-A", "name": "Plan A"}).data
    member = admin_client.post(
        "/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data
    quote = admin_client.post(
        "/api/v1/quotes",
        {"proposerId": proposer["id"], "planId": plan["id"], "effectiveDate": "2026-06-01"},
        format="json",
    ).data

    from apps.policy.domain.enums import PolicyMemberStatus, PolicyType
    from apps.policy.infrastructure.models import Policy, PolicyMember
    from apps.quote.infrastructure.models import Quote, QuoteSnapshot

    quote_obj = Quote.all_tenants.get(id=quote["id"])
    benefits = admin_client.get(f"/api/v1/plans/{plan['id']}/benefits").data
    snapshot = QuoteSnapshot.all_tenants.create(
        tenant_id=tenant.id,
        quote=quote_obj,
        snapshot_no=1,
        snapshot_type="APPROVAL",
        plan_id=plan["id"],
        snapshot_json={"plan": {"planId": plan["id"], "benefits": [{"code": b["benefit"]["code"]} for b in benefits]}},
        checksum="test-checksum",
        created_by="actor-1",
    )
    policy = Policy.all_tenants.create(
        tenant_id=tenant.id,
        policy_number=policy_number,
        source_quote=quote_obj,
        contracted_terms_snapshot=snapshot,
        proposer_id=proposer["id"],
        plan_id=plan["id"],
        policy_type=PolicyType.INDIVIDUAL.value,
        term_months=12,
        status="ACTIVE",
        start_date=_START_DATE,
        end_date=_END_DATE,
        payment_frequency="ANUAL",
        currency_code="AOA",
        issued_by="actor-1",
    )
    PolicyMember.all_tenants.create(
        tenant_id=tenant.id,
        policy=policy,
        member_id=member["id"],
        status=PolicyMemberStatus.ACTIVE.value,
        inclusion_date=_START_DATE,
    )

    return {
        "quoteId": quote["id"],
        "policyId": str(policy.id),
        "policyNumber": policy_number,
        "registrationNumber": registration_number,
        "proposerId": proposer["id"],
        "memberId": member["id"],
        "planId": plan["id"],
    }


def _login(tenant, scope: dict) -> str:
    client = APIClient()
    client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {"policyNumber": scope["policyNumber"], "registrationNumber": scope["registrationNumber"], "email": _EMAIL},
        format="json",
    )
    otp = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    response = client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
        {
            "policyNumber": scope["policyNumber"],
            "registrationNumber": scope["registrationNumber"],
            "email": _EMAIL,
            "otp": otp,
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    return response.data["accessToken"]


def _portal_client(token: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.django_db
def test_me_lists_only_own_policies(admin_client, tenant):
    mine = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ME-001", registration_number="111111111LA011")
    _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ME-002", registration_number="222222222LA022")

    token = _login(tenant, mine)
    response = _portal_client(token).get("/api/v1/customer-portal/me")

    assert response.status_code == 200
    policy_numbers = [item["policy"]["policyNumber"] for item in response.data["policies"]]
    assert policy_numbers == ["APO-ME-001"]
    assert response.data["policies"][0]["plan"]["id"] == mine["planId"]
    assert response.data["policies"][0]["outstandingInstallments"] == {"count": 0, "totalAmount": "0.00"}


@pytest.mark.django_db
def test_me_requires_a_portal_token():
    response = APIClient().get("/api/v1/customer-portal/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_me_reports_outstanding_installments(admin_client, tenant):
    mine = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ME-003", registration_number="151515151LA015")

    from apps.policy.infrastructure.models import PremiumInstallment

    PremiumInstallment.all_tenants.create(
        tenant_id=tenant.id,
        policy_id=mine["policyId"],
        installment_no=1,
        period_from=_START_DATE,
        period_to=_END_DATE,
        due_date=_START_DATE,
        amount="500.00",
        currency_code="AOA",
        status="OVERDUE",
    )

    token = _login(tenant, mine)
    response = _portal_client(token).get("/api/v1/customer-portal/me")

    assert response.status_code == 200
    assert response.data["policies"][0]["outstandingInstallments"] == {"count": 1, "totalAmount": "500.00"}


@pytest.mark.django_db
def test_plan_benefits_returns_contracted_coverages(admin_client, tenant):
    scope = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-COV-001", registration_number="333333333LA033")
    token = _login(tenant, scope)

    response = _portal_client(token).get(f"/api/v1/customer-portal/plan-benefits?policyNumber={scope['policyNumber']}")

    assert response.status_code == 200
    codes = [b["benefit"]["code"] for b in response.data["benefits"]]
    assert "HOSPITALIZATION" in codes  # core benefit auto-attached at plan creation


@pytest.mark.django_db
def test_plan_benefits_is_404_for_a_policy_not_belonging_to_the_caller(admin_client, tenant):
    mine = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-COV-002", registration_number="444444444LA044")
    _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-COV-003", registration_number="555555555LA055")
    token = _login(tenant, mine)

    response = _portal_client(token).get("/api/v1/customer-portal/plan-benefits?policyNumber=APO-COV-003")
    assert response.status_code == 404


@pytest.mark.django_db
def test_coverage_checks_own_member_and_is_covered_today(admin_client, tenant):
    scope = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-COVCHK-001", registration_number="666666666LA066")
    token = _login(tenant, scope)

    response = _portal_client(token).get(
        f"/api/v1/customer-portal/coverage?policyNumber={scope['policyNumber']}&date=2026-06-15"
    )
    assert response.status_code == 200, response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["memberId"] == scope["memberId"]
    assert response.data["results"][0]["covered"] is True


@pytest.mark.django_db
def test_coverage_is_404_for_a_policy_not_belonging_to_the_caller(admin_client, tenant):
    mine = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-COVCHK-002", registration_number="777777777LA077")
    _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-COVCHK-003", registration_number="888888888LA088")
    token = _login(tenant, mine)

    response = _portal_client(token).get("/api/v1/customer-portal/coverage?policyNumber=APO-COVCHK-003")
    assert response.status_code == 404


@pytest.mark.django_db
def test_eligibility_endpoint_also_checks_coverage_for_own_members_only(admin_client, tenant):
    scope = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ELIG-001", registration_number="999999999LA099")
    token = _login(tenant, scope)

    response = _portal_client(token).post(
        "/api/v1/customer-portal/eligibility", {"policyNumber": scope["policyNumber"], "date": "2026-06-15"}, format="json"
    )

    assert response.status_code == 200, response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["memberId"] == scope["memberId"]
    assert response.data["results"][0]["covered"] is True


@pytest.mark.django_db
def test_eligibility_rejects_a_memberid_not_on_the_caller_policy(admin_client, tenant):
    mine = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ELIG-002", registration_number="101010101LA010")
    other = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ELIG-003", registration_number="121212121LA012")
    token = _login(tenant, mine)

    response = _portal_client(token).post(
        "/api/v1/customer-portal/eligibility",
        {"policyNumber": mine["policyNumber"], "memberId": other["memberId"]},
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_eligibility_rejects_a_policy_not_belonging_to_the_caller(admin_client, tenant):
    mine = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ELIG-004", registration_number="131313131LA013")
    _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-ELIG-005", registration_number="141414141LA014")
    token = _login(tenant, mine)

    response = _portal_client(token).post(
        "/api/v1/customer-portal/eligibility", {"policyNumber": "APO-ELIG-005"}, format="json"
    )
    assert response.status_code == 404


def _set_quote(scope: dict, **fields) -> None:
    from apps.quote.infrastructure.models import Quote

    Quote.all_tenants.filter(id=scope["quoteId"]).update(**fields)


@pytest.mark.django_db
def test_my_quotes_lists_only_own_quotes_with_translated_status(admin_client, tenant):
    mine = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-Q-001", registration_number="771111111LA011")
    _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-Q-002", registration_number="772222222LA022")
    token = _login(tenant, mine)
    _set_quote(mine, status="BOUND")  # the fixture quote is a DRAFT, which the portal hides

    response = _portal_client(token).get("/api/v1/customer-portal/me/quotes")

    assert response.status_code == 200, response.data
    quotes = response.data["quotes"]
    assert len(quotes) == 1
    assert quotes[0]["policyNumber"] == "APO-Q-001"
    assert quotes[0]["status"] == "CONTRACTED"
    assert quotes[0]["plan"]["name"] == "Plan A"
    assert set(quotes[0]) == {
        "quoteNumber", "status", "effectiveDate", "validUntil", "product", "plan",
        "totalAmount", "currencyCode", "policyNumber", "createdAt",
    }


@pytest.mark.django_db
def test_my_quotes_hides_drafts_and_expires_stale_approved_quotes(admin_client, tenant):
    scope = _setup_active_policy_with_member(admin_client, tenant, policy_number="APO-Q-003", registration_number="773333333LA033")
    token = _login(tenant, scope)
    client = _portal_client(token)

    _set_quote(scope, status="DRAFT")
    assert client.get("/api/v1/customer-portal/me/quotes").data["quotes"] == []

    _set_quote(scope, status="APPROVED", valid_until=datetime.date.today() + datetime.timedelta(days=5))
    assert client.get("/api/v1/customer-portal/me/quotes").data["quotes"][0]["status"] == "AWAITING_SIGNATURE"

    _set_quote(scope, valid_until=datetime.date.today() - datetime.timedelta(days=1))
    assert client.get("/api/v1/customer-portal/me/quotes").data["quotes"][0]["status"] == "EXPIRED"

    _set_quote(scope, status="IN_REVIEW")
    assert client.get("/api/v1/customer-portal/me/quotes").data["quotes"][0]["status"] == "IN_REVIEW"
    assert client.get("/api/v1/customer-portal/me/quotes").data["quotes"][0]["totalAmount"] is None


@pytest.mark.django_db
def test_my_quotes_requires_a_portal_token():
    assert APIClient().get("/api/v1/customer-portal/me/quotes").status_code == 401



# ---- PDF MVP read endpoints (portal_views.py) ------------------------------
def _contracted(admin_client, tenant, number: str, reg: str) -> tuple[dict, APIClient]:
    scope = _setup_active_policy_with_member(admin_client, tenant, policy_number=number, registration_number=reg)
    _set_quote(scope, status="BOUND")
    return scope, _portal_client(_login(tenant, scope))


@pytest.mark.django_db
def test_policy_detail_lists_members_and_is_404_for_someone_elses(admin_client, tenant):
    mine, client = _contracted(admin_client, tenant, "APO-R-001", "881111111LA011")
    other, _ = _contracted(admin_client, tenant, "APO-R-002", "882222222LA022")

    response = client.get(f"/api/v1/customer-portal/policies/{mine['policyNumber']}")
    assert response.status_code == 200, response.data
    assert response.data["policyNumber"] == "APO-R-001"
    assert len(response.data["members"]) == 1
    assert response.data["members"][0]["relationship"] == "TITULAR"
    assert client.get(f"/api/v1/customer-portal/policies/{other['policyNumber']}").status_code == 404


@pytest.mark.django_db
def test_policies_list_filters_by_phase(admin_client, tenant):
    _, client = _contracted(admin_client, tenant, "APO-R-003", "883333333LA033")
    everything = client.get("/api/v1/customer-portal/policies").data["policies"]
    assert [p["policyNumber"] for p in everything] == ["APO-R-003"]
    assert client.get("/api/v1/customer-portal/policies?phase=CANCELLED").data["policies"] == []
    assert client.get("/api/v1/customer-portal/policies?phase=NOPE").status_code == 400


@pytest.mark.django_db
def test_quote_detail_has_timeline_and_hides_other_quotes(admin_client, tenant):
    mine, client = _contracted(admin_client, tenant, "APO-R-004", "884444444LA044")
    _set_quote(mine, quote_number="Q-R-004")

    response = client.get("/api/v1/customer-portal/me/quotes/Q-R-004")
    assert response.status_code == 200, response.data
    codes = [e["code"] for e in response.data["timeline"]]
    assert codes[0] == "QUOTE_CREATED"
    assert "POLICY_ISSUED" in codes
    assert client.get("/api/v1/customer-portal/me/quotes/NOPE").status_code == 404


@pytest.mark.django_db
def test_payments_and_dashboard_report_overdue(admin_client, tenant):
    mine, client = _contracted(admin_client, tenant, "APO-R-005", "885555555LA055")
    from apps.policy.infrastructure.models import PremiumInstallment

    PremiumInstallment.all_tenants.create(
        tenant_id=tenant.id, policy_id=mine["policyId"], installment_no=1, period_from=_START_DATE,
        period_to=_END_DATE, due_date=_START_DATE, amount="500.00", currency_code="AOA", status="OVERDUE",
    )
    payments = client.get("/api/v1/customer-portal/payments").data
    assert payments["totals"] == [{"currencyCode": "AOA", "paid": "0.00", "pending": "0.00", "overdue": "500.00"}]
    assert client.get("/api/v1/customer-portal/payments?status=PAID").data["installments"] == []

    dashboard = client.get("/api/v1/customer-portal/dashboard").data
    assert dashboard["quotes"]["byStatus"] == {"CONTRACTED": 1}
    assert any(a["code"] == "PAYMENT_OVERDUE" for a in dashboard["alerts"])
    assert dashboard["financial"][0]["overdue"] == "500.00"


@pytest.mark.django_db
def test_beneficiaries_card_profile_and_documents(admin_client, tenant):
    mine, client = _contracted(admin_client, tenant, "APO-R-006", "886666666LA066")

    people = client.get("/api/v1/customer-portal/beneficiaries").data["beneficiaries"]
    assert [p["policyNumber"] for p in people] == ["APO-R-006"]

    card = client.get(f"/api/v1/customer-portal/policies/{mine['policyNumber']}/members/{mine['memberId']}/card")
    assert card.status_code == 200, card.data
    assert card.data["policyNumber"] == "APO-R-006"
    assert card.data["memberNumber"] == mine["memberId"].split("-")[0].upper()
    nobody = "00000000-0000-0000-0000-000000000000"
    assert client.get(
        f"/api/v1/customer-portal/policies/{mine['policyNumber']}/members/{nobody}/card"
    ).status_code == 404

    profile = client.get("/api/v1/customer-portal/profile").data
    assert profile["accountEmail"] == _EMAIL
    assert profile["proposers"][0]["registrationNumber"] == "886666666LA066"

    assert client.get("/api/v1/customer-portal/documents").data == {"documents": []}
    assert client.get(f"/api/v1/customer-portal/documents/{nobody}/download").status_code == 404


@pytest.mark.django_db
def test_new_portal_endpoints_require_a_portal_token():
    client = APIClient()
    for path in ("dashboard", "policies", "beneficiaries", "payments", "documents", "profile", "me/quotes/X"):
        assert client.get(f"/api/v1/customer-portal/{path}").status_code == 401, path
