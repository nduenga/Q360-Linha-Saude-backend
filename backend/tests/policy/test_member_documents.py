"""Documentos em falta: enviar → analisar → pessoa elegível, coberta e ativa."""
from __future__ import annotations

import datetime

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from tests.customer_portal.test_self_service_api import _portal_client
from tests.policy.test_issuance import (
    _eligibility_rule,
    _nif_for_suffix,
    _parameter_set,
    _plan,
    _rating_table,
    _approver,
)

PDF = b"%PDF-1.4\n% documento de teste\n"
_RULE = {"categoryRules": {"ASCENDANT": {"requiresCohabitationOrFinancialDependency": True}}}
_SIGN = {
    "signatoryName": "Holder", "signatoryDocumentType": "BI", "signatoryDocumentNumber": "000000000BI000",
    "signatoryCapacity": "TOMADOR", "termMonths": 12, "paymentFrequency": "ANUAL", "signedAt": "2026-06-10T14:00:00Z",
}
_PAYMENT = {"paidAt": "2026-06-10T15:00:00Z", "paymentMethod": "NUMERARIO"}


def _file(name="comprovativo.pdf", content=PDF, content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def _setup(admin_client, suffix: str) -> dict:
    """Plano + configuração + titular e um ascendente que precisa de prova de dependência."""
    plan_ref = _plan(admin_client, product_code=f"MD-{suffix}")
    _parameter_set(admin_client, code=f"MD-PARAMS-{suffix}")
    _rating_table(admin_client, code=f"MD-TABLE-{suffix}")
    _eligibility_rule(admin_client, code=f"MD-ELIG-{suffix}", config=_RULE)
    proposer = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "Holder", "registrationNumber": _nif_for_suffix(suffix),
         "email": "holder@example.com", "phone": "+244900000000"},
    ).data["id"]
    holder = admin_client.post(
        "/api/v1/members", {"proposerId": proposer, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data["id"]
    parent = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer, "relationshipCode": "ASCENDENTE", "firstName": "Rosa", "lastName": "Silva", "dateOfBirth": "1960-01-01"},
    ).data["id"]
    quote = admin_client.post(
        "/api/v1/quotes", {**plan_ref, "proposerId": proposer, "effectiveDate": "2026-06-01"}, format="json"
    ).data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": holder}, format="json")
    return {"quoteId": quote["id"], "proposerId": proposer, "holderId": holder, "parentId": parent, "planId": plan_ref["planId"]}


@pytest.mark.django_db
def test_missing_document_blocks_the_member_and_an_approved_one_clears_it_in_the_quote(admin_client, tenant):
    scope = _setup(admin_client, "Q1")
    added = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/members", {"memberId": scope["parentId"]}, format="json")
    assert added.status_code in (200, 201), added.data

    def quote_member_status():
        from apps.quote.infrastructure.models import QuoteMember

        return QuoteMember.all_tenants.get(quote_id=scope["quoteId"], member_id=scope["parentId"]).status

    assert quote_member_status() == "REFERRAL"
    listing = admin_client.get(f"/api/v1/members/{scope['parentId']}/documents").data
    assert listing["documents"] == []
    pending = listing["pending"]
    assert len(pending) == 1 and pending[0]["documentType"] == "DEPENDENCY_PROOF" and pending[0]["context"] == "QUOTE"

    uploaded = admin_client.post(
        f"/api/v1/members/{scope['parentId']}/documents",
        {"file": _file(), "evidenceType": "DEPENDENCY_PROOF", "note": "Declaração da junta"}, format="multipart",
    )
    assert uploaded.status_code == 201, uploaded.data
    assert uploaded.data["status"] == "SUBMITTED"
    assert quote_member_status() == "REFERRAL"  # só enviar não chega: falta a análise

    queue = admin_client.get("/api/v1/member-documents").data["items"]
    assert [d["id"] for d in queue] == [uploaded.data["id"]] and queue[0]["memberName"] == "Rosa Silva"
    download = admin_client.get(f"/api/v1/member-documents/{uploaded.data['id']}/download")
    assert download.status_code == 200 and download.content == PDF

    reviewed = _approver(tenant).post(
        f"/api/v1/member-documents/{uploaded.data['id']}/review", {"decision": "APPROVE"}, format="json"
    )
    assert reviewed.status_code == 200, reviewed.data
    assert reviewed.data["document"]["status"] == "APPROVED"
    assert reviewed.data["reevaluation"]["quoteMembers"][0]["to"] == "INCLUDED"
    assert quote_member_status() == "INCLUDED"
    assert admin_client.get(f"/api/v1/members/{scope['parentId']}/documents").data["pending"] == []
    again = _approver(tenant).post(f"/api/v1/member-documents/{uploaded.data['id']}/review", {"decision": "APPROVE"}, format="json")
    assert again.status_code == 409 and "já foi analisado" in again.data["detail"]


@pytest.mark.django_db
def test_rejection_needs_a_reason_and_keeps_the_member_pending(admin_client, tenant):
    scope = _setup(admin_client, "Q2")
    admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/members", {"memberId": scope["parentId"]}, format="json")
    document = admin_client.post(
        f"/api/v1/members/{scope['parentId']}/documents", {"file": _file(), "evidenceType": "DEPENDENCY_PROOF"}, format="multipart"
    ).data
    approver = _approver(tenant)
    no_reason = approver.post(f"/api/v1/member-documents/{document['id']}/review", {"decision": "REJECT"}, format="json")
    assert no_reason.status_code == 409 and "motivo" in no_reason.data["detail"]
    rejected = approver.post(
        f"/api/v1/member-documents/{document['id']}/review", {"decision": "REJECT", "note": "Ilegível"}, format="json"
    )
    assert rejected.status_code == 200 and rejected.data["document"]["status"] == "REJECTED"
    from apps.quote.infrastructure.models import QuoteMember

    assert QuoteMember.all_tenants.get(quote_id=scope["quoteId"], member_id=scope["parentId"]).status == "REFERRAL"


@pytest.mark.django_db
def test_upload_validation_is_in_portuguese(admin_client):
    scope = _setup(admin_client, "Q3")
    url = f"/api/v1/members/{scope['parentId']}/documents"
    bad_type = admin_client.post(url, {"file": _file("x.exe", b"MZ", "application/x-msdownload"), "evidenceType": "OTHER"}, format="multipart")
    assert bad_type.status_code == 400 and "Formato de ficheiro não suportado" in bad_type.data["detail"]
    empty = admin_client.post(url, {"file": _file("x.pdf", b""), "evidenceType": "OTHER"}, format="multipart")
    assert empty.status_code == 400
    wrong = admin_client.post(url, {"file": _file(), "evidenceType": "NOPE"}, format="multipart")
    assert wrong.status_code == 400


@pytest.mark.django_db
def test_approved_document_activates_the_pending_policy_member_with_waiting_periods(admin_client, tenant):
    """Apólice em vigor com a pessoa pendente: o documento aprovado ativa-a, regista o
    endosso e a cobertura passa a existir."""
    from apps.eligibility.infrastructure.models import EligibilityEvaluation
    from apps.policy.infrastructure.models import Policy, PolicyEndorsement, PolicyMember
    from tests.policy.test_issuance import _approved_quote

    quote = _approved_quote(admin_client, tenant, suffix="Q4")
    # a regra usada em _approved_quote não tem regras de categoria: publica-se uma nova versão com elas
    admin_client.post(
        "/api/v1/rule-versions",
        {"code": "MD-ELIG-Q4-CAT", "name": "cat", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-02-01",
         "artifactType": "JSON", "artifactRef": __import__("json").dumps(_RULE)}, format="json",
    )
    rules = admin_client.get("/api/v1/rule-versions").data
    created = next(r for r in (rules["items"] if isinstance(rules, dict) else rules) if r["code"] == "MD-ELIG-Q4-CAT")
    admin_client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")

    policy = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy/emit", {**_SIGN, "rowVersion": quote["rowVersion"], "payment": _PAYMENT}, format="json"
    ).data
    assert policy["status"] == "ACTIVE"

    parent = admin_client.post(
        "/api/v1/members",
        {"proposerId": quote["proposerId"], "relationshipCode": "ASCENDENTE", "firstName": "Rosa", "lastName": "Silva", "dateOfBirth": "1960-01-01"},
    ).data["id"]
    plan_id = Policy.all_tenants.get(id=policy["id"]).plan_id
    evaluation = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {"proposerId": quote["proposerId"], "memberId": parent, "planId": str(plan_id), "effectiveDate": "2026-06-11", "context": {}},
        format="json",
    )
    assert evaluation.status_code == 200 and evaluation.data["decision"] == "PENDING_DOCUMENT", evaluation.data
    evaluation_row = EligibilityEvaluation.all_tenants.get(id=evaluation.data["evaluationId"])
    PolicyMember.all_tenants.create(
        tenant_id=tenant.id, policy_id=policy["id"], member_id=parent, status="PENDING",
        pending_reason_code="FALTA_PROVA_DEPENDENCIA_ASCENDENTE", eligibility_evaluation=evaluation_row, rule_version=evaluation_row.rule_version,
    )
    before = admin_client.get(f"/api/v1/policies/{policy['id']}/coverage", {"memberId": parent, "date": "2026-07-01"})
    assert before.status_code == 200 and before.data["covered"] is False

    document = admin_client.post(
        f"/api/v1/members/{parent}/documents", {"file": _file(), "evidenceType": "DEPENDENCY_PROOF"}, format="multipart"
    ).data
    reviewed = _approver(tenant).post(f"/api/v1/member-documents/{document['id']}/review", {"decision": "APPROVE"}, format="json")
    assert reviewed.status_code == 200, reviewed.data
    change = reviewed.data["reevaluation"]["policyMembers"][0]
    assert change["to"] == "ACTIVE" and change["endorsementNo"] == 1

    row = PolicyMember.all_tenants.get(policy_id=policy["id"], member_id=parent)
    assert row.status == "ACTIVE" and row.pending_reason_code is None and row.inclusion_date == datetime.date.today()
    assert PolicyEndorsement.all_tenants.filter(policy_id=policy["id"], endorsement_type="ACTIVATE_MEMBER").count() == 1
    after = admin_client.get(f"/api/v1/policies/{policy['id']}/coverage", {"memberId": parent, "date": datetime.date.today().isoformat()})
    assert after.status_code == 200
    assert after.data.get("reasonCode") != "MEMBER_PENDING"


@pytest.mark.django_db
def test_customer_uploads_from_the_portal_and_is_notified_of_the_decision(admin_client, tenant):
    from tests.policy.test_issuance import _approved_quote

    quote = _approved_quote(admin_client, tenant, suffix="Q5")
    policy = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy/emit", {**_SIGN, "rowVersion": quote["rowVersion"], "payment": _PAYMENT}, format="json"
    ).data
    parent = admin_client.post(
        "/api/v1/members",
        {"proposerId": quote["proposerId"], "relationshipCode": "ASCENDENTE", "firstName": "Rosa", "lastName": "Silva", "dateOfBirth": "1960-01-01"},
    ).data["id"]

    credentials = {"policyNumber": policy["policyNumber"], "registrationNumber": _nif_for_suffix("Q5"), "email": "holder@example.com"}
    anonymous = APIClient()
    anonymous.post(f"/api/v1/customer-portal/{tenant.id}/auth/request-access", credentials, format="json")
    otp = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    token = anonymous.post(f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp", {**credentials, "otp": otp}, format="json").data["accessToken"]
    portal = _portal_client(token)
    base = f"/api/v1/customer-portal/members/{parent}/documents"

    assert portal.get(base).status_code == 200 and portal.get(base).data["documents"] == []
    sent = portal.post(base, {"file": _file(), "evidenceType": "DEPENDENCY_PROOF", "note": "Vive comigo"}, format="multipart")
    assert sent.status_code == 201, sent.data
    assert sent.data["status"] == "SUBMITTED" and sent.data["submittedBy"] == "CUSTOMER"
    assert [d["id"] for d in portal.get(base).data["documents"]] == [sent.data["id"]]
    # a pessoa segura de outro cliente nunca é acessível
    other_proposer = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "Outro", "registrationNumber": _nif_for_suffix("Q5X"),
         "email": "outro@example.com", "phone": "+244900000001"},
    ).data["id"]
    other_member = admin_client.post(
        "/api/v1/members", {"proposerId": other_proposer, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data["id"]
    assert portal.get(f"/api/v1/customer-portal/members/{other_member}/documents").status_code == 404

    _approver(tenant).post(
        f"/api/v1/member-documents/{sent.data['id']}/review", {"decision": "REJECT", "note": "Falta a assinatura"}, format="json"
    )
    notifications = portal.get("/api/v1/customer-portal/notifications").data["notifications"]
    mine = [n for n in notifications if n["code"] == "MEMBER_DOCUMENT_REVIEWED"]
    assert mine and "recusado" in mine[0]["title"].lower() and "Falta a assinatura" in mine[0]["body"]
