"""Integration tests for the Fase 1 self-service endpoints
(ROADMAP_PORTAL_CLIENTE.md) — GET /me, GET /coverage, POST /eligibility.
Same django_db style as test_portal_auth_api.py; not runnable in this
sandbox (no Docker/Postgres) but written for CI, same as the existing
eligibility API test precedent.
"""
from __future__ import annotations

import pytest
from django.core import mail
from rest_framework.test import APIClient

_EMAIL = "cliente@example.com"


def _setup_quote_with_member(admin_client, *, quote_number: str, registration_number: str) -> dict:
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
    product = admin_client.post(
        "/api/v1/products", {"code": f"PORTAL-{quote_number}", "name": "Portal Product"}
    ).data
    plan = admin_client.post(
        "/api/v1/plans", {"productId": product["id"], "code": "PLAN-A", "name": "Plan A"}
    ).data

    member = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"},
    ).data

    quote = admin_client.post(
        "/api/v1/quotes",
        {
            "proposerId": proposer["id"],
            "planId": plan["id"],
            "effectiveDate": "2026-06-01",
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json")

    from apps.quote.infrastructure.models import Quote

    Quote.all_tenants.filter(id=quote["id"]).update(status="APPROVED", quote_number=quote_number)

    return {
        "quoteId": quote["id"],
        "quoteNumber": quote_number,
        "registrationNumber": registration_number,
        "proposerId": proposer["id"],
        "memberId": member["id"],
        "planId": plan["id"],
    }


def _login(tenant, scope: dict) -> str:
    client = APIClient()
    client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {"quoteNumber": scope["quoteNumber"], "registrationNumber": scope["registrationNumber"], "email": _EMAIL},
        format="json",
    )
    otp = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    response = client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
        {
            "quoteNumber": scope["quoteNumber"],
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
def test_me_lists_only_own_quotes(admin_client, tenant):
    mine = _setup_quote_with_member(admin_client, quote_number="Q-ME-001", registration_number="111111111LA011")
    _setup_quote_with_member(admin_client, quote_number="Q-ME-002", registration_number="222222222LA022")

    token = _login(tenant, mine)
    response = _portal_client(token).get("/api/v1/customer-portal/me")

    assert response.status_code == 200
    quote_numbers = [item["quote"]["quoteNumber"] for item in response.data["quotes"]]
    assert quote_numbers == ["Q-ME-001"]
    assert response.data["quotes"][0]["plan"]["id"] == mine["planId"]


@pytest.mark.django_db
def test_me_requires_a_portal_token():
    response = APIClient().get("/api/v1/customer-portal/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_coverage_returns_plan_benefits(admin_client, tenant):
    scope = _setup_quote_with_member(admin_client, quote_number="Q-COV-001", registration_number="333333333LA033")
    token = _login(tenant, scope)

    response = _portal_client(token).get(f"/api/v1/customer-portal/coverage?quoteNumber={scope['quoteNumber']}")

    assert response.status_code == 200
    codes = [b["benefit"]["code"] for b in response.data["benefits"]]
    assert "HOSPITALIZATION" in codes  # core benefit auto-attached at plan creation


@pytest.mark.django_db
def test_coverage_is_404_for_a_quote_not_belonging_to_the_caller(admin_client, tenant):
    mine = _setup_quote_with_member(admin_client, quote_number="Q-COV-002", registration_number="444444444LA044")
    _setup_quote_with_member(admin_client, quote_number="Q-COV-003", registration_number="555555555LA055")
    token = _login(tenant, mine)

    response = _portal_client(token).get("/api/v1/customer-portal/coverage?quoteNumber=Q-COV-003")
    assert response.status_code == 404


@pytest.mark.django_db
def test_eligibility_evaluates_own_members_only(admin_client, tenant):
    scope = _setup_quote_with_member(admin_client, quote_number="Q-ELIG-001", registration_number="666666666LA066")
    token = _login(tenant, scope)

    response = _portal_client(token).post(
        "/api/v1/customer-portal/eligibility", {"quoteNumber": scope["quoteNumber"]}, format="json"
    )

    assert response.status_code == 200, response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["memberId"] == scope["memberId"]
    # No published ELIGIBILITY rule version -> CONFIG_ERROR, fail-closed,
    # same contract as the staff endpoint.
    assert response.data["results"][0]["decision"] == "CONFIG_ERROR"


@pytest.mark.django_db
def test_eligibility_rejects_a_memberid_not_on_the_caller_quote(admin_client, tenant):
    mine = _setup_quote_with_member(admin_client, quote_number="Q-ELIG-002", registration_number="777777777LA077")
    other = _setup_quote_with_member(admin_client, quote_number="Q-ELIG-003", registration_number="888888888LA088")
    token = _login(tenant, mine)

    response = _portal_client(token).post(
        "/api/v1/customer-portal/eligibility",
        {"quoteNumber": mine["quoteNumber"], "memberId": other["memberId"]},
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_eligibility_rejects_a_quote_not_belonging_to_the_caller(admin_client, tenant):
    mine = _setup_quote_with_member(admin_client, quote_number="Q-ELIG-004", registration_number="999999999LA099")
    _setup_quote_with_member(admin_client, quote_number="Q-ELIG-005", registration_number="101010101LA010")
    token = _login(tenant, mine)

    response = _portal_client(token).post(
        "/api/v1/customer-portal/eligibility", {"quoteNumber": "Q-ELIG-005"}, format="json"
    )
    assert response.status_code == 404
