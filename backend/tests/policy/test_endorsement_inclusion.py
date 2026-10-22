"""Endosso de inclusão: pessoa nova numa apólice ativa, prémio pro-rata
repartido pelas prestações que faltam, aprovação e aceitação do cliente."""
from __future__ import annotations

import datetime
from decimal import Decimal, ROUND_HALF_UP

import pytest

from tests.policy.test_issuance import _approved_quote, _approver


def _active_policy(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="END")
    approver = _approver(tenant)
    policy = approver.post(f"/api/v1/quotes/{quote['id']}/policy", {
        "signatoryName": "Holder", "signatoryDocumentType": "BI", "signatoryDocumentNumber": "000000000BI000",
        "signatoryCapacity": "TOMADOR", "termMonths": 12, "paymentFrequency": "MENSAL",
        "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]}, format="json").data
    approver.post(f"/api/v1/policies/{policy['id']}/installments/1/payment",
                  {"paidAt": "2026-06-10T16:00:00Z", "rowVersion": policy["rowVersion"]}, format="json")
    return admin_client.get(f"/api/v1/policies/{policy['id']}").data, quote


@pytest.mark.django_db
def test_inclusion_prorata_approval_and_client_acceptance(admin_client, tenant):
    policy, quote = _active_policy(admin_client, tenant)
    assert policy["status"] == "ACTIVE"
    child = admin_client.post("/api/v1/members", {"proposerId": quote["proposerId"], "relationshipCode": "FILHO",
                                                  "dateOfBirth": "2015-03-01"}).data["id"]
    today = datetime.date.today()
    url = f"/api/v1/policies/{policy['id']}/endorsements/inclusions"
    assert admin_client.post(url, {"inclusionDate": (today - datetime.timedelta(days=1)).isoformat(),
                                   "memberIds": [child]}, format="json").status_code == 400
    assert admin_client.post(url, {"inclusionDate": today.isoformat(), "memberIds": [quote["memberId"]]},
                             format="json").status_code == 400  # já está na apólice
    inclusion = today + datetime.timedelta(days=10)
    created = admin_client.post(url, {"inclusionDate": inclusion.isoformat(), "memberIds": [child]}, format="json")
    assert created.status_code == 201, created.data
    calc = created.data["calculation"]
    start = datetime.date.fromisoformat(policy["startDate"])
    end = datetime.date.fromisoformat(policy["endDate"])
    remaining, basis = (end - inclusion).days + 1, (end - start).days + 1
    assert calc["days"] == {"remaining": remaining, "basis": basis, "basisCode": "ACTUAL_PERIOD",
                            "factor": str((Decimal(remaining) / Decimal(basis)).quantize(Decimal("0.000001")))}
    expected = (Decimal(calc["annualPremium"]) * remaining / basis).quantize(Decimal("0.01"), ROUND_HALF_UP)
    assert Decimal(calc["proRataPremium"]) == expected
    assert sum(Decimal(i["amount"]) for i in calc["installments"]) == Decimal(calc["totalCharged"])
    assert all(i["dueDate"] >= inclusion.isoformat() for i in calc["installments"])
    qid = created.data["quoteId"]
    assert admin_client.post(url, {"inclusionDate": inclusion.isoformat()}, format="json").status_code == 409

    ready = admin_client.get(f"/api/v1/quotes/{qid}").data
    submitted = admin_client.post(f"/api/v1/quotes/{qid}/submit", {"rowVersion": ready["rowVersion"]}, format="json")
    assert submitted.status_code == 200, submitted.data
    approved = _approver(tenant).post(f"/api/v1/quotes/{qid}/decision", {
        "decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted.data["rowVersion"]}, format="json")
    assert approved.status_code == 200, approved.data
    offer = admin_client.get(f"/api/v1/quotes/{qid}/endorsement").data
    assert offer["status"] == "APPROVED" and offer["acceptanceDeadline"] == inclusion.isoformat()

    before = len(admin_client.get(f"/api/v1/policies/{policy['id']}/installments").data)
    accepted = _approver(tenant).post(f"/api/v1/quotes/{qid}/endorsement/response", {"decision": "ACCEPT"}, format="json")
    assert accepted.status_code == 200, accepted.data
    assert accepted.data["status"] == "BOUND" and accepted.data["appliedEndorsementNo"] == 1
    members = admin_client.get(f"/api/v1/policies/{policy['id']}/members").data
    assert any(m["memberId"] == child for m in members)
    installments = admin_client.get(f"/api/v1/policies/{policy['id']}/installments").data
    assert len(installments) == before + len(calc["installments"])
    listed = admin_client.get(f"/api/v1/policies/{policy['id']}/endorsements").data
    assert listed["endorsements"][0]["type"] == "ADD_MEMBER"
    html = admin_client.get(f"/api/v1/quotes/{qid}/endorsement/document", {"fileType": "html"})
    assert html.status_code == 200 and "Ata adicional n.º 1" in html.content.decode()
    assert "Prémio pro-rata" in html.content.decode()
    pdf = admin_client.get(f"/api/v1/quotes/{qid}/endorsement/document")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def _child(admin_client, proposer_id, birth: datetime.date) -> str:
    created = admin_client.post("/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "FILHO",
                                                    "dateOfBirth": birth.isoformat()})
    assert created.status_code == 201, created.data
    return created.data["id"]


def _publish_settings(admin_client, tenant, values: dict) -> None:
    from tests.policy.conftest import make_client

    base = "/api/v1/business-config/configurations"
    created = admin_client.post(base, {"configKey": "policy.endorsements", "value": {"endorsements": values},
                                       "effectiveFrom": "2026-01-01"}, format="json")
    assert created.status_code == 201, created.data
    assert admin_client.post(f"{base}/{created.data['id']}", {"action": "submit"}, format="json").status_code == 200
    other = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin q360.approve",
                        actor_id="config-approver")
    assert other.post(f"{base}/{created.data['id']}/approve").status_code == 200


def _submit(admin_client, qid):
    ready = admin_client.get(f"/api/v1/quotes/{qid}").data
    response = admin_client.post(f"/api/v1/quotes/{qid}/submit", {"rowVersion": ready["rowVersion"]}, format="json")
    assert response.status_code == 200, response.data
    return response.data


def _open_and_approve(admin_client, tenant, policy, member_id, inclusion) -> str:
    created = admin_client.post(f"/api/v1/policies/{policy['id']}/endorsements/inclusions",
                                {"inclusionDate": inclusion.isoformat(), "memberIds": [member_id]}, format="json")
    assert created.status_code == 201, created.data
    qid = created.data["quoteId"]
    submitted = _submit(admin_client, qid)
    approved = _approver(tenant).post(f"/api/v1/quotes/{qid}/decision", {
        "decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]}, format="json")
    assert approved.status_code == 200, approved.data
    return qid


@pytest.mark.django_db
def test_newborn_is_included_automatically_with_minimum_premium_and_fixed_basis(admin_client, tenant):
    policy, quote = _active_policy(admin_client, tenant)
    _publish_settings(admin_client, tenant, {"day_count_basis": "FIXED_366", "minimum_premium": "999999",
                                             "newborn_auto_inclusion_days": 30, "acceptance_days": 5})
    today = datetime.date.today()
    inclusion = today + datetime.timedelta(days=10)
    baby = _child(admin_client, quote["proposerId"], today - datetime.timedelta(days=5))
    created = admin_client.post(f"/api/v1/policies/{policy['id']}/endorsements/inclusions",
                                {"inclusionDate": inclusion.isoformat(), "memberIds": [baby]}, format="json")
    assert created.status_code == 201, created.data
    calc = created.data["calculation"]
    assert calc["days"]["basis"] == 366 and calc["days"]["basisCode"] == "FIXED_366"
    assert calc["minimumApplied"] is True and calc["endorsementPremium"] == "999999.00"
    assert calc["newbornAutoInclusion"] is True and calc["members"][0]["newborn"] is True
    qid = created.data["quoteId"]
    requirements = admin_client.get(f"/api/v1/quotes/{qid}/requirements").data
    codes = {(i["code"], i.get("memberId")) for i in requirements["info"] + requirements["warnings"]}
    assert ("NEWBORN_AUTO_INCLUSION", baby) in codes
    assert ("CLINICAL_QUESTIONNAIRE_REQUIRED", baby) not in codes

    submitted = _submit(admin_client, qid)
    assert submitted["status"] == "APPROVED"  # sem revisão manual
    offer = admin_client.get(f"/api/v1/quotes/{qid}/endorsement").data
    assert offer["autoApproved"] is True
    assert offer["acceptanceDeadline"] == (today + datetime.timedelta(days=5)).isoformat()
    assert offer["calculation"]["endorsementPremium"] == "999999.00"  # congelado na submissão


@pytest.mark.django_db
def test_date_change_refusal_expiry_and_no_policy_from_endorsement(admin_client, tenant):
    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.tenant import TenantId
    from apps.quote.infrastructure.models import Quote

    policy, quote = _active_policy(admin_client, tenant)
    today = datetime.date.today()
    first = _child(admin_client, quote["proposerId"], datetime.date(2016, 1, 1))
    created = admin_client.post(f"/api/v1/policies/{policy['id']}/endorsements/inclusions",
                                {"inclusionDate": (today + datetime.timedelta(days=5)).isoformat(),
                                 "memberIds": [first]}, format="json").data
    qid = created["quoteId"]
    changed = admin_client.put(f"/api/v1/quotes/{qid}/endorsement",
                               {"inclusionDate": (today + datetime.timedelta(days=40)).isoformat()}, format="json")
    assert changed.status_code == 200, changed.data
    assert changed.data["calculation"]["days"]["remaining"] == created["calculation"]["days"]["remaining"] - 35
    assert admin_client.put(f"/api/v1/quotes/{qid}/endorsement", {"inclusionDate": "2020-01-01"},
                            format="json").status_code == 400

    submitted = _submit(admin_client, qid)
    approved = _approver(tenant).post(f"/api/v1/quotes/{qid}/decision", {
        "decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]}, format="json").data
    issue = _approver(tenant).post(f"/api/v1/quotes/{qid}/policy", {
        "signatoryName": "Holder", "signatoryDocumentType": "BI", "signatoryDocumentNumber": "000000000BI000",
        "signatoryCapacity": "TOMADOR", "termMonths": 12, "paymentFrequency": "ANUAL",
        "signedAt": "2026-06-10T14:00:00Z", "rowVersion": approved["rowVersion"]}, format="json")
    assert issue.status_code >= 400 and "endosso" in issue.data["detail"]
    response_url = f"/api/v1/quotes/{qid}/endorsement/response"
    assert _approver(tenant).post(response_url, {"decision": "REFUSE"}, format="json").status_code == 400
    refused = _approver(tenant).post(response_url, {"decision": "REFUSE", "reason": "O cliente desistiu da inclusão"},
                                     format="json")
    assert refused.status_code == 200 and refused.data["status"] == "CANCELLED"
    members = admin_client.get(f"/api/v1/policies/{policy['id']}/members").data
    assert not any(m["memberId"] == first for m in members)

    # Prazo de aceitação ultrapassado: a proposta expira e já não se aplica.
    second = _child(admin_client, quote["proposerId"], datetime.date(2017, 1, 1))
    qid2 = _open_and_approve(admin_client, tenant, policy, second, today + datetime.timedelta(days=20))
    token = CurrentActorProvider.bind(Actor(actor_id="t", tenant_id=TenantId(tenant.id), roles=frozenset()))
    try:
        row = Quote.objects.get(id=qid2)
        Quote.objects.filter(id=qid2).update(endorsement_json={**row.endorsement_json, "acceptanceDeadline": "2026-01-01"})
    finally:
        CurrentActorProvider.reset(token)
    import io

    from django.core.management import call_command

    out = io.StringIO()
    call_command("expire_endorsement_offers", stdout=out)
    assert "1 endorsement offer(s) expired" in out.getvalue()
    assert admin_client.get(f"/api/v1/quotes/{qid2}/endorsement").data["status"] == "EXPIRED"
    history = admin_client.get(f"/api/v1/quotes/{qid2}/history").data
    assert history[-1]["reasonCode"] == "ENDORSEMENT_ACCEPTANCE_DEADLINE"
    assert _approver(tenant).post(f"/api/v1/quotes/{qid2}/endorsement/response", {"decision": "ACCEPT"},
                                  format="json").status_code == 409


@pytest.mark.django_db
def test_client_accepts_the_endorsement_in_the_portal(admin_client, tenant):
    from django.core import mail
    from rest_framework.test import APIClient

    policy, quote = _active_policy(admin_client, tenant)
    today = datetime.date.today()
    child = _child(admin_client, quote["proposerId"], datetime.date(2014, 5, 5))
    qid = _open_and_approve(admin_client, tenant, policy, child, today + datetime.timedelta(days=7))

    proposer = admin_client.get(f"/api/v1/proposers/{quote['proposerId']}").data
    client = APIClient()
    client.post(f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
                {"policyNumber": policy["policyNumber"], "registrationNumber": proposer["registrationNumber"],
                 "email": "holder@example.com"}, format="json")
    otp = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    login = client.post(f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
                        {"policyNumber": policy["policyNumber"], "registrationNumber": proposer["registrationNumber"],
                         "email": "holder@example.com", "otp": otp}, format="json")
    assert login.status_code == 200, login.data
    portal = APIClient()
    portal.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['accessToken']}")
    offers = portal.get("/api/v1/customer-portal/endorsements").data
    assert [o["quoteId"] for o in offers] == [qid] and offers[0]["calculation"]["totalCharged"]
    assert portal.post(f"/api/v1/customer-portal/endorsements/{qid}/response", {"decision": "MAYBE"},
                       format="json").status_code == 400
    pdf = portal.get(f"/api/v1/customer-portal/endorsements/{qid}/document")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    accepted = portal.post(f"/api/v1/customer-portal/endorsements/{qid}/response", {"decision": "ACCEPT"}, format="json")
    assert accepted.status_code == 200, accepted.data
    assert accepted.data["status"] == "BOUND" and accepted.data["clientResponse"]["channel"] == "PORTAL"
    assert portal.get("/api/v1/customer-portal/endorsements").data == []
