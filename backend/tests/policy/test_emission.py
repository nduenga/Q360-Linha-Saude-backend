"""Emissão da apólice num só passo (rascunho pré-preenchido → assinatura +
pagamento → apólice digital), pela API real."""
from __future__ import annotations

import pytest

from tests.policy.test_issuance import _approved_quote, _approver

_BODY = {
    "signatoryName": "Holder",
    "signatoryDocumentType": "BI",
    "signatoryDocumentNumber": "000000000BI000",
    "signatoryCapacity": "TOMADOR",
    "termMonths": 12,
    "paymentFrequency": "ANUAL",
    "signedAt": "2026-06-10T14:00:00Z",
}
_PAYMENT = {"paidAt": "2026-06-10T15:00:00Z", "paymentMethod": "TRANSFERENCIA", "paymentReference": "TRF-001"}


@pytest.mark.django_db
def test_draft_is_prefilled_from_the_approved_quote(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="E1")
    response = admin_client.get(f"/api/v1/quotes/{quote['id']}/policy-draft")
    assert response.status_code == 200, response.data
    draft = response.data
    assert draft["canEmit"] is True and draft["blockingReason"] is None
    assert draft["rowVersion"] == quote["rowVersion"]
    assert draft["holder"]["name"] == "Holder"
    assert draft["premium"]["total"] == "1200.00"
    assert draft["defaults"]["termMonths"] == 12
    assert draft["defaults"]["signatory"]["name"] == "Holder"
    assert [i["amount"] for i in draft["installmentsPreview"]["SEMESTRAL"]] == ["600.00", "600.00"]
    assert len(draft["installmentsPreview"]["MENSAL"]) == 12
    assert [m["policyStatus"] for m in draft["members"]] == ["ACTIVE"]
    assert draft["terms"] is not None and "exclusions" in draft["terms"]


@pytest.mark.django_db
def test_emit_with_payment_activates_the_policy_and_generates_the_document(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="E2")
    approver = _approver(tenant)
    response = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy/emit",
        {**_BODY, "rowVersion": quote["rowVersion"], "payment": _PAYMENT},
        format="json",
    )
    assert response.status_code == 201, response.data
    policy = response.data
    assert policy["status"] == "ACTIVE"
    assert policy["startDate"] == "2026-06-11" and policy["endDate"] == "2027-06-10"
    assert policy["documentPath"] == f"/api/v1/policies/{policy['id']}/document"

    installments = admin_client.get(f"/api/v1/policies/{policy['id']}/installments").data
    assert installments[0]["status"] == "PAID" and installments[0]["paymentReference"] == "TRF-001"

    document = admin_client.get(policy["documentPath"])
    assert document.status_code == 200
    assert document["Content-Type"] == "application/pdf"
    assert document.content.startswith(b"%PDF")

    html = admin_client.get(policy["documentPath"], {"fileType": "html"})
    assert html.status_code == 200
    page = html.content.decode()
    assert policy["policyNumber"] in page and "Exclusões" in page and "Plano de pagamento" in page

    draft = admin_client.get(f"/api/v1/quotes/{quote['id']}/policy-draft").data
    assert draft["canEmit"] is False and draft["policyId"] == policy["id"]


@pytest.mark.django_db
def test_emit_without_payment_leaves_the_policy_waiting_for_the_first_premium(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="E3")
    response = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy/emit", {**_BODY, "rowVersion": quote["rowVersion"]}, format="json"
    )
    assert response.status_code == 201, response.data
    assert response.data["status"] == "PENDING_FIRST_PREMIUM"
    assert admin_client.get(response.data["documentPath"]).status_code == 200


@pytest.mark.django_db
def test_emit_is_all_or_nothing_and_never_twice(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="E4")
    approver = _approver(tenant)
    bad = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy/emit",
        {**_BODY, "rowVersion": quote["rowVersion"], "requestedStartDate": "2026-06-10", "payment": _PAYMENT},
        format="json",
    )
    assert bad.status_code == 400  # start date not after the signature date
    assert admin_client.get(f"/api/v1/quotes/{quote['id']}").data["status"] == "APPROVED"

    ok = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy/emit",
        {**_BODY, "rowVersion": quote["rowVersion"], "payment": _PAYMENT},
        format="json",
    )
    assert ok.status_code == 201
    again = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy/emit",
        {**_BODY, "rowVersion": quote["rowVersion"], "payment": _PAYMENT},
        format="json",
    )
    assert again.status_code == 409


# ------------------------------------------------------------------ portal
@pytest.mark.django_db
def test_customer_sees_the_policy_and_gets_statements_without_asking(admin_client, tenant):
    from rest_framework.test import APIClient

    from django.core import mail
    from tests.customer_portal.test_self_service_api import _portal_client
    from tests.policy.test_issuance import _nif_for_suffix

    quote = _approved_quote(admin_client, tenant, suffix="E5")
    policy = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy/emit",
        {**_BODY, "rowVersion": quote["rowVersion"], "payment": _PAYMENT},
        format="json",
    ).data

    credentials = {"policyNumber": policy["policyNumber"], "registrationNumber": _nif_for_suffix("E5"), "email": "holder@example.com"}
    anonymous = APIClient()
    anonymous.post(f"/api/v1/customer-portal/{tenant.id}/auth/request-access", credentials, format="json")
    otp = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    token = anonymous.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp", {**credentials, "otp": otp}, format="json"
    ).data["accessToken"]
    portal = _portal_client(token)
    base = "/api/v1/customer-portal"

    documents = portal.get(f"{base}/documents").data["documents"]
    item = next(d for d in documents if d["type"] == "APOLICE")
    assert item["policyNumber"] == policy["policyNumber"]
    download = portal.get(f"{base}/documents/{item['id']}/download")
    assert download.status_code == 200 and download.content.startswith(b"%PDF")
    assert portal.get(f"{base}/policies/{policy['policyNumber']}/document").content.startswith(b"%PDF")

    coverage = portal.get(f"{base}/policies/{policy['policyNumber']}/statement?kind=COVERAGE")
    assert coverage.status_code == 200 and coverage.content.startswith(b"%PDF")
    receipt = portal.get(f"{base}/policies/{policy['policyNumber']}/statement?kind=PAYMENT")
    assert receipt.status_code == 200 and receipt.content.startswith(b"%PDF")
    assert portal.get(f"{base}/policies/{policy['policyNumber']}/statement?kind=NOPE").status_code == 400

    types = {t["code"]: t for t in portal.get(f"{base}/request-types").data["types"]}
    assert types["DOCUMENT_COPY"]["selfService"] is True and types["STATEMENT"]["selfService"] is True
    assert types["RENEWAL"]["selfService"] is False


@pytest.mark.django_db
def test_emitting_closes_the_customers_acceptance_request(admin_client, tenant):
    from apps.customer_portal.infrastructure.models import PortalRequest
    from apps.quote.infrastructure.models import Quote

    quote = _approved_quote(admin_client, tenant, suffix="E6")
    from apps.client.infrastructure.models import Proposer
    from apps.customer_portal.infrastructure.models import CustomerAccount

    account = CustomerAccount.all_tenants.create(tenant_id=tenant.id, email="holder@example.com")
    request = PortalRequest.all_tenants.create(
        tenant_id=tenant.id, request_number="PED-TEST-1", customer_account_id=account.id,
        proposer_id=quote["proposerId"], quote_id=quote["id"], request_type="ACCEPT_QUOTE", subject="Aceitar", status="OPEN",
    )
    _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy/emit", {**_BODY, "rowVersion": quote["rowVersion"], "payment": _PAYMENT}, format="json"
    )
    request.refresh_from_db()
    assert request.status == "COMPLETED"
    assert "emitida" in (request.resolution_note or "")
