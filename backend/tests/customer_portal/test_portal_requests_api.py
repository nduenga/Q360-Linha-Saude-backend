"""Pedidos ao seguro, mensagens, notificações, renovação e comparação de planos
(Portal_Cliente_Sistema_Cotacoes_Saude.pdf, s.8, 11, 12, 14, 15)."""
from __future__ import annotations

import datetime

import pytest
from rest_framework.test import APIClient

from django.core import mail

from tests.customer_portal.test_self_service_api import (
    _portal_client,
    _set_quote,
    _setup_active_policy_with_member,
)

BASE = "/api/v1/customer-portal"


def _login_as(tenant, scope: dict, email: str) -> str:
    """One account per email (OD-PORTAL-002 links every proposer an email logs in
    with), so each test customer needs its own email to stay isolated."""
    client = APIClient()
    credentials = {"policyNumber": scope["policyNumber"], "registrationNumber": scope["registrationNumber"], "email": email}
    client.post(f"/api/v1/customer-portal/{tenant.id}/auth/request-access", credentials, format="json")
    otp = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    response = client.post(f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp", {**credentials, "otp": otp}, format="json")
    assert response.status_code == 200, response.data
    return response.data["accessToken"]


def _customer(admin_client, tenant, number: str, reg: str):
    scope = _setup_active_policy_with_member(admin_client, tenant, policy_number=number, registration_number=reg)
    _set_quote(scope, status="BOUND", quote_number=f"Q-{number}")
    return scope, _portal_client(_login_as(tenant, scope, f"{number.lower()}@example.com"))


def _ask(client, request_type="OTHER", **extra):
    return client.post(f"{BASE}/requests", {"requestType": request_type, **extra}, format="json")


# ---------------------------------------------------------------- pedidos
@pytest.mark.django_db
def test_create_request_and_list_only_own(admin_client, tenant):
    mine, client = _customer(admin_client, tenant, "APO-P-001", "901111111LA011")
    _, other = _customer(admin_client, tenant, "APO-P-002", "902222222LA022")

    created = _ask(client, "DATA_CHANGE", subject="Mudar morada", description="Nova morada", policyNumber=mine["policyNumber"])
    assert created.status_code == 201, created.data
    assert created.data["status"] == "OPEN"
    assert created.data["requestNumber"].startswith("PED-")
    assert [h["status"] for h in created.data["history"]] == ["OPEN"]

    assert [r["requestNumber"] for r in client.get(f"{BASE}/requests").data["requests"]] == [created.data["requestNumber"]]
    assert other.get(f"{BASE}/requests").data["requests"] == []
    assert other.get(f"{BASE}/requests/{created.data['requestNumber']}").status_code == 404


@pytest.mark.django_db
def test_request_validation(admin_client, tenant):
    mine, client = _customer(admin_client, tenant, "APO-P-003", "903333333LA033")
    other, _ = _customer(admin_client, tenant, "APO-P-004", "904444444LA044")

    assert _ask(client, "NOPE").status_code == 400
    assert _ask(client, "CANCELLATION").status_code == 400  # needs a policy
    assert _ask(client, "DATA_CHANGE", policyNumber=other["policyNumber"]).status_code == 404  # not mine
    assert _ask(client, "MEMBER_INCLUSION", policyNumber=mine["policyNumber"], payload={"firstName": "Ana"}).status_code == 400
    assert _ask(client, "MEMBER_EXCLUSION", policyNumber=mine["policyNumber"],
                payload={"memberId": other["memberId"]}).status_code == 400
    ok = _ask(client, "MEMBER_EXCLUSION", policyNumber=mine["policyNumber"], payload={"memberId": mine["memberId"]})
    assert ok.status_code == 201, ok.data
    inclusion = _ask(
        client, "MEMBER_INCLUSION", policyNumber=mine["policyNumber"],
        payload={"firstName": "Ana", "lastName": "Silva", "dateOfBirth": "2015-05-05", "relationship": "FILHO"},
    )
    assert inclusion.status_code == 201, inclusion.data


@pytest.mark.django_db
def test_renewal_only_inside_the_window_and_only_one_open(admin_client, tenant):
    from apps.policy.infrastructure.models import Policy

    mine, client = _customer(admin_client, tenant, "APO-P-005", "905555555LA055")
    assert _ask(client, "RENEWAL", policyNumber=mine["policyNumber"]).status_code == 400  # ends 2027-06-01

    Policy.all_tenants.filter(id=mine["policyId"]).update(end_date=datetime.date.today() + datetime.timedelta(days=30))
    first = _ask(client, "RENEWAL", policyNumber=mine["policyNumber"])
    assert first.status_code == 201, first.data
    assert _ask(client, "RENEWAL", policyNumber=mine["policyNumber"]).status_code == 409


@pytest.mark.django_db
def test_new_quote_request_needs_no_policy(admin_client, tenant):
    _, client = _customer(admin_client, tenant, "APO-P-006", "906666666LA066")
    created = _ask(client, "NEW_QUOTE", description="Quero cotação para a minha família", payload={"people": 4})
    assert created.status_code == 201, created.data
    assert created.data["policyNumber"] is None


@pytest.mark.django_db
def test_accept_quote_needs_an_approved_valid_quote(admin_client, tenant):
    scope, client = _customer(admin_client, tenant, "APO-P-007", "907777777LA077")
    assert _ask(client, "ACCEPT_QUOTE", quoteNumber="Q-APO-P-007").status_code == 400  # BOUND, not awaiting

    _set_quote(scope, status="APPROVED", valid_until=datetime.date.today() + datetime.timedelta(days=5))
    assert _ask(client, "ACCEPT_QUOTE", quoteNumber="Q-APO-P-007").status_code == 201
    assert _ask(client, "ACCEPT_QUOTE", quoteNumber="Q-APO-P-007").status_code == 409


# ------------------------------------------------------- backoffice + estados
@pytest.mark.django_db
def test_staff_moves_a_request_and_the_customer_is_notified(admin_client, tenant):
    mine, client = _customer(admin_client, tenant, "APO-P-008", "908888888LA088")
    number = _ask(client, "DOCUMENT_COPY", description="Segunda via da apólice").data["requestNumber"]

    listing = admin_client.get("/api/v1/portal-requests?status=OPEN")
    assert listing.status_code == 200, listing.data
    assert [r["requestNumber"] for r in listing.data["requests"]] == [number]
    assert listing.data["requests"][0]["customerName"] == "Cliente Teste"

    def move(to, note=None):
        return admin_client.post(f"/api/v1/portal-requests/{number}/transition", {"toStatus": to, "note": note}, format="json")

    assert move("COMPLETED").status_code == 409  # OPEN cannot jump to COMPLETED
    assert move("IN_REVIEW").status_code == 200
    assert move("REJECTED").status_code == 400  # a rejection needs a note
    waiting = move("AWAITING_CUSTOMER", "Envie o seu BI.")
    assert waiting.status_code == 200, waiting.data
    assert waiting.data["status"] == "AWAITING_CUSTOMER"

    detail = client.get(f"{BASE}/requests/{number}").data
    assert [h["status"] for h in detail["history"]] == ["OPEN", "IN_REVIEW", "AWAITING_CUSTOMER"]
    assert detail["history"][-1]["note"] == "Envie o seu BI."

    notices = client.get(f"{BASE}/notifications").data
    assert any(n["code"] == "REQUEST_UPDATED" and "A aguardar o cliente" in n["title"] for n in notices["notifications"])

    # the customer's answer puts it back in analysis
    reply = client.post(f"{BASE}/messages", {"contextType": "REQUEST", "contextRef": number, "body": "Segue o BI."}, format="json")
    assert reply.status_code == 201, reply.data
    assert client.get(f"{BASE}/requests/{number}").data["status"] == "IN_REVIEW"


@pytest.mark.django_db
def test_customer_cannot_use_the_staff_endpoints(admin_client, tenant):
    _, client = _customer(admin_client, tenant, "APO-P-009", "909999999LA099")
    assert client.get("/api/v1/portal-requests").status_code in (401, 403)
    assert client.post("/api/v1/portal-messages", {"contextType": "POLICY", "contextRef": "X", "body": "x"}, format="json").status_code in (401, 403)


# --------------------------------------------------------------- mensagens
@pytest.mark.django_db
def test_messages_are_contextual_scoped_and_tracked_as_unread(admin_client, tenant):
    mine, client = _customer(admin_client, tenant, "APO-M-001", "911111111LA011")
    _, other = _customer(admin_client, tenant, "APO-M-002", "912222222LA022")
    ref = mine["policyNumber"]

    assert client.post(f"{BASE}/messages", {"contextType": "POLICY", "contextRef": ref, "body": "Olá"}, format="json").status_code == 201
    assert other.post(f"{BASE}/messages", {"contextType": "POLICY", "contextRef": ref, "body": "x"}, format="json").status_code == 404
    assert client.post(f"{BASE}/messages", {"contextType": "POLICY", "contextRef": ref, "body": "  "}, format="json").status_code == 400
    assert client.post(f"{BASE}/messages", {"contextType": "CHAT", "contextRef": ref, "body": "x"}, format="json").status_code == 400

    inbox = admin_client.get("/api/v1/portal-conversations?unread=true").data["conversations"]
    assert [(c["contextRef"], c["unread"]) for c in inbox] == [(ref, 1)]
    assert inbox[0]["customerName"] == "Cliente Teste"

    reply = admin_client.post("/api/v1/portal-messages", {"contextType": "POLICY", "contextRef": ref, "body": "Bom dia!"}, format="json")
    assert reply.status_code == 201, reply.data
    assert admin_client.get(f"/api/v1/portal-messages?contextType=POLICY&contextRef={ref}").status_code == 200
    assert admin_client.get("/api/v1/portal-conversations?unread=true").data["conversations"] == []

    convo = client.get(f"{BASE}/conversations").data["conversations"]
    assert [(c["contextRef"], c["unread"]) for c in convo] == [(ref, 1)]
    assert "proposerId" not in convo[0]

    thread = client.get(f"{BASE}/messages?contextType=POLICY&contextRef={ref}").data["messages"]
    assert [(m["from"], m["body"]) for m in thread] == [("CUSTOMER", "Olá"), ("STAFF", "Bom dia!")]
    assert client.get(f"{BASE}/conversations").data["conversations"][0]["unread"] == 0
    assert other.get(f"{BASE}/messages?contextType=POLICY&contextRef={ref}").status_code == 404
    assert any(n["code"] == "NEW_MESSAGE" for n in client.get(f"{BASE}/notifications").data["notifications"])


# ------------------------------------------------------------ notificações
@pytest.mark.django_db
def test_notifications_are_derived_idempotent_and_markable(admin_client, tenant):
    from apps.policy.infrastructure.models import PremiumInstallment

    mine, client = _customer(admin_client, tenant, "APO-N-001", "921111111LA011")
    PremiumInstallment.all_tenants.create(
        tenant_id=tenant.id, policy_id=mine["policyId"], installment_no=1,
        period_from=datetime.date(2026, 6, 2), period_to=datetime.date(2027, 6, 1),
        due_date=datetime.date(2026, 6, 2), amount="500.00", currency_code="AOA", status="OVERDUE",
    )

    first = client.get(f"{BASE}/notifications").data
    codes = sorted(n["code"] for n in first["notifications"])
    assert "POLICY_ISSUED" in codes and "PAYMENT_OVERDUE" in codes
    assert first["unreadCount"] == len(codes)

    again = client.get(f"{BASE}/notifications").data
    assert len(again["notifications"]) == len(first["notifications"])  # no duplicates

    one = first["notifications"][0]["id"]
    assert client.post(f"{BASE}/notifications/read", {"ids": [one]}, format="json").data == {"updated": 1}
    assert client.get(f"{BASE}/notifications").data["unreadCount"] == first["unreadCount"] - 1
    assert len(client.get(f"{BASE}/notifications?unread=true").data["notifications"]) == first["unreadCount"] - 1
    assert client.post(f"{BASE}/notifications/read", {}, format="json").data["updated"] == first["unreadCount"] - 1
    assert client.get(f"{BASE}/notifications").data["unreadCount"] == 0


@pytest.mark.django_db
def test_an_approved_quote_raises_a_notification(admin_client, tenant):
    scope, client = _customer(admin_client, tenant, "APO-N-002", "922222222LA022")
    _set_quote(scope, status="APPROVED", valid_until=datetime.date.today() + datetime.timedelta(days=30))
    codes = [n["code"] for n in client.get(f"{BASE}/notifications").data["notifications"]]
    assert "QUOTE_APPROVED" in codes


@pytest.mark.django_db
def test_notifications_require_a_portal_token():
    assert APIClient().get(f"{BASE}/notifications").status_code == 401


# --------------------------------------------------------------- renovação
@pytest.mark.django_db
def test_renewal_journey_steps(admin_client, tenant):
    from apps.policy.infrastructure.models import Policy

    mine, client = _customer(admin_client, tenant, "APO-R-101", "931111111LA011")
    url = f"{BASE}/policies/{mine['policyNumber']}/renewal"

    far = client.get(url).data
    assert far["canRequest"] is False
    assert far["currentTerms"]["plan"]["name"] == "Plan A"
    assert [s["state"] for s in far["steps"]][0] == "CURRENT"

    Policy.all_tenants.filter(id=mine["policyId"]).update(end_date=datetime.date.today() + datetime.timedelta(days=30))
    near = client.get(url).data
    assert near["canRequest"] is True
    assert [s["state"] for s in near["steps"]][:3] == ["DONE", "DONE", "CURRENT"]

    assert _ask(client, "RENEWAL", policyNumber=mine["policyNumber"]).status_code == 201
    after = client.get(url).data
    assert after["canRequest"] is False
    assert after["request"]["status"] == "OPEN"
    states = {s["code"]: s["state"] for s in after["steps"]}
    assert states["REQUEST"] == "DONE" and states["PROPOSAL"] == "CURRENT"

    other, _ = _customer(admin_client, tenant, "APO-R-102", "932222222LA022")
    assert client.get(f"{BASE}/policies/{other['policyNumber']}/renewal").status_code == 404


# ------------------------------------------------------ comparação de planos
@pytest.mark.django_db
def test_plan_comparison_lists_plans_of_the_product_without_prices(admin_client, tenant):
    mine, client = _customer(admin_client, tenant, "APO-C-001", "941111111LA011")
    product_id = admin_client.get("/api/v1/products").data["items"][0]["id"]
    maternity_id = next(
        b["id"] for b in admin_client.get("/api/v1/benefits?category=COMPLEMENTARY").data["items"] if b["code"] == "MATERNITY"
    )
    created = admin_client.post(
        "/api/v1/plans",
        {"productId": product_id, "code": "PLAN-B", "name": "Plan B", "complementaryBenefitIds": [maternity_id]},
        format="json",
    )
    assert created.status_code == 201, created.data

    response = client.get(f"{BASE}/plans/compare?policyNumber={mine['policyNumber']}")
    assert response.status_code == 200, response.data
    plans = {p["name"]: p for p in response.data["plans"]}
    assert plans["Plan A"]["isCurrent"] is True
    assert any(b["code"] == "HOSPITALIZATION" for b in plans["Plan A"]["benefits"])
    assert any(b["code"] == "MATERNITY" for b in plans["Plan B"]["benefits"])
    assert not any(b["code"] == "MATERNITY" for b in plans["Plan A"]["benefits"])
    assert {b["code"] for b in response.data["benefits"]} >= {"HOSPITALIZATION", "MATERNITY"}
    # only coverage data: no price/tariff fields at any level
    assert not {"premium", "price", "amountDue", "totalAmount", "tariff"} & set(str(response.data).replace("'", " ").split())

    assert client.get(f"{BASE}/plans/compare").status_code == 400
    other, _ = _customer(admin_client, tenant, "APO-C-002", "942222222LA022")
    assert client.get(f"{BASE}/plans/compare?policyNumber={other['policyNumber']}").status_code == 404
