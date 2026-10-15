"""Integration tests for the customer portal's public pre-auth endpoints
(ROADMAP_PORTAL_CLIENTE.md Fase 0, migrated to Policy in Fase 6 —
DECISIONS_TAKEN.md#S09-POLICY-001) against a real Postgres — same
`@pytest.mark.django_db` style as tests/eligibility/test_evaluate_api.py.

Policy issuance/activation itself is out of scope here (apps.policy has
its own test suite for that, tests/policy/test_issuance.py); this file
builds a Policy directly via `all_tenants.create(...)`, mirroring
test_evaluate_api.py's own precedent for out-of-workflow setup
(`Plan.all_tenants.filter(...).update(...)`).
"""
from __future__ import annotations

import datetime

import pytest
from django.core import mail
from rest_framework.test import APIClient

_REGISTRATION_NUMBER = "123456789LA042"
_EMAIL = "cliente@example.com"


def _setup_active_policy(admin_client, tenant) -> dict:
    proposer = admin_client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "dateOfBirth": "1985-04-12", "displayName": "Cliente Teste",
            "registrationNumber": _REGISTRATION_NUMBER,
            "email": _EMAIL,
            "phone": "+244900000000",
        },
    ).data
    product = admin_client.post("/api/v1/products", {"code": "PORTAL-PROD", "name": "Portal Product"}).data
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "PLAN-A", "name": "Plan A"}).data
    quote = admin_client.post(
        "/api/v1/quotes",
        {"proposerId": proposer["id"], "planId": plan["id"]},
        format="json",
    ).data

    from apps.policy.domain.enums import PolicyType
    from apps.policy.infrastructure.models import Policy
    from apps.quote.infrastructure.models import Quote, QuoteSnapshot

    quote_obj = Quote.all_tenants.get(id=quote["id"])
    snapshot = QuoteSnapshot.all_tenants.create(
        tenant_id=tenant.id,
        quote=quote_obj,
        snapshot_no=1,
        snapshot_type="APPROVAL",
        plan_id=plan["id"],
        snapshot_json={"plan": {"planId": plan["id"], "benefits": []}},
        checksum="test-checksum",
        created_by="actor-1",
    )
    Policy.all_tenants.create(
        tenant_id=tenant.id,
        policy_number="APO-PORTAL-0001",
        source_quote=quote_obj,
        contracted_terms_snapshot=snapshot,
        proposer_id=proposer["id"],
        plan_id=plan["id"],
        policy_type=PolicyType.INDIVIDUAL.value,
        term_months=12,
        status="ACTIVE",
        start_date=datetime.date(2026, 6, 2),
        end_date=datetime.date(2027, 6, 1),
        payment_frequency="ANUAL",
        currency_code="AOA",
        issued_by="actor-1",
    )
    return {"policyNumber": "APO-PORTAL-0001", "registrationNumber": _REGISTRATION_NUMBER}


def _otp_from_outbox() -> str:
    body = mail.outbox[-1].body
    return body.split(": ", 1)[1].splitlines()[0].strip()


@pytest.mark.django_db
def test_request_access_sends_otp_email_for_valid_policy_and_document(admin_client, tenant):
    scope = _setup_active_policy(admin_client, tenant)
    client = APIClient()

    response = client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {**scope, "email": _EMAIL},
        format="json",
    )
    assert response.status_code == 202
    assert len(mail.outbox) == 1
    assert _EMAIL in mail.outbox[0].to


@pytest.mark.django_db
def test_request_access_reports_policy_not_found_for_a_nonexistent_policy(tenant):
    # Product Owner decision (2026-09-26): no longer a silent 202 — see
    # apps.customer_portal.domain.errors module docstring.
    client = APIClient()
    response = client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {"policyNumber": "DOES-NOT-EXIST", "registrationNumber": "000000000LA000", "email": _EMAIL},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["code"] == "PORTAL-POLICY-NOT-FOUND"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_request_access_reports_registration_mismatch_for_a_real_policy(admin_client, tenant):
    # Same Product Owner decision as above: a real policyNumber with the
    # wrong registrationNumber is now distinguishable from a nonexistent one.
    scope = _setup_active_policy(admin_client, tenant)
    client = APIClient()
    response = client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {"policyNumber": scope["policyNumber"], "registrationNumber": "000000000LA000", "email": _EMAIL},
        format="json",
    )
    assert response.status_code == 401
    assert response.data["code"] == "PORTAL-REGISTRATION-MISMATCH"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_full_login_flow_issues_a_token(admin_client, tenant):
    scope = _setup_active_policy(admin_client, tenant)
    client = APIClient()
    client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {**scope, "email": _EMAIL},
        format="json",
    )
    otp = _otp_from_outbox()

    response = client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
        {**scope, "email": _EMAIL, "otp": otp},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["accessToken"]
    assert response.data["tokenType"] == "Bearer"


@pytest.mark.django_db
def test_wrong_otp_is_401_and_the_fifth_failure_locks_the_account(admin_client, tenant):
    scope = _setup_active_policy(admin_client, tenant)
    client = APIClient()
    client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {**scope, "email": _EMAIL},
        format="json",
    )

    def _attempt():
        return client.post(
            f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
            {**scope, "email": _EMAIL, "otp": "000000"},
            format="json",
        )

    for _ in range(4):
        response = _attempt()
        assert response.status_code == 401, response.data

    locked_response = _attempt()
    assert locked_response.status_code == 423, locked_response.data


@pytest.mark.django_db
def test_correct_otp_after_lockout_is_still_rejected_until_window_expires(admin_client, tenant):
    scope = _setup_active_policy(admin_client, tenant)
    client = APIClient()
    client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {**scope, "email": _EMAIL},
        format="json",
    )
    otp = _otp_from_outbox()

    for _ in range(5):
        client.post(
            f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
            {**scope, "email": _EMAIL, "otp": "000000"},
            format="json",
        )

    response = client.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
        {**scope, "email": _EMAIL, "otp": otp},
        format="json",
    )
    assert response.status_code == 423, response.data
