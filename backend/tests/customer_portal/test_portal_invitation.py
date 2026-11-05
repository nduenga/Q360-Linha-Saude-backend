"""Ao registar um proponente com email, o cliente recebe o link do Portal do
Cliente e consegue criar a palavra-passe sem ter ainda apólice nem cotação."""
from __future__ import annotations

from unittest import mock

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer

BASE = "/api/v1/customer-portal"


@pytest.fixture(autouse=True)
def _no_ip_limit(settings):
    settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP = 0
    settings.CUSTOMER_PORTAL_URL = "https://portal.exemplo.ao/portal-cliente"


def _create(admin_client, *, email, nif, kind="INDIVIDUAL"):
    body = {"proposerType": kind, "displayName": "Empresa Convite, Lda.", "registrationNumber": nif,
            "email": email, "phone": "+244923000000"}
    if kind == "INDIVIDUAL":
        body["dateOfBirth"] = "1990-01-01"
    response = admin_client.post("/api/v1/proposers", body, format="json")
    assert response.status_code == 201, response.data
    return response.data


@pytest.mark.django_db(transaction=True)
def test_new_proposer_gets_portal_link_and_can_set_password(admin_client, tenant):
    mail.outbox.clear()
    proposer = _create(admin_client, email="rh@convite.ao", nif="023239343LA090")

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["rh@convite.ao"]
    assert "https://portal.exemplo.ao/portal-cliente/recuperar?email=rh%40convite.ao&convite=1" in message.body
    account = CustomerAccount.all_tenants.get(tenant_id=tenant.id, email="rh@convite.ao")
    assert account.password_hash is None
    assert CustomerAccountProposer.all_tenants.filter(customer_account=account, proposer_id=proposer["id"]).exists()

    # o link leva a «definir palavra-passe»: o pedido de código já encontra a conta
    sent = APIClient().post(f"{BASE}/{tenant.id}/auth/password-reset/request", {"email": "rh@convite.ao"}, format="json")
    assert sent.status_code in (200, 202, 204), sent.data
    assert mail.outbox[-1].to == ["rh@convite.ao"] and len(mail.outbox) == 2


@pytest.mark.django_db(transaction=True)
def test_existing_account_is_not_linked_automatically(admin_client, tenant):
    """O mesmo email noutro cliente (p.ex. o do mediador) não dá acesso sozinho."""
    first = _create(admin_client, email="mediador@convite.ao", nif="023239343LA091")
    second = _create(admin_client, email="mediador@convite.ao", nif="023239343LA092")
    account = CustomerAccount.all_tenants.get(tenant_id=tenant.id, email="mediador@convite.ao")
    linked = set(CustomerAccountProposer.all_tenants.filter(customer_account=account).values_list("proposer_id", flat=True))
    assert {str(x) for x in linked} == {first["id"]}
    assert "Primeiro acesso" in mail.outbox[-1].body and "/primeiro?" in mail.outbox[-1].body
    assert second["id"] not in {str(x) for x in linked}


@pytest.mark.django_db(transaction=True)
def test_organisation_contact_does_not_get_portal_invitation_before_titular_import(admin_client):
    mail.outbox.clear()
    _create(
        admin_client,
        email="empresa@convite.ao",
        nif="5417000005",
        kind="ORGANISATION",
    )
    assert mail.outbox == []


def test_no_email_no_invitation():
    """Sem email não há convite (p.ex. proponente criado na cotação sem email)."""
    import uuid

    from apps.client.infrastructure.models import Proposer
    from apps.customer_portal.application.invitation_service import invite_proposer

    proposer = Proposer(id=uuid.uuid4(), email="", display_name="X")
    assert invite_proposer(proposer) is None


_ORG_TITULAR = {"firstName": "Marta", "lastName": "Neto", "dateOfBirth": "1985-03-02", "sexCode": "F",
                "email": "marta@convite.ao", "phone": "+244923111222"}


def _organisation_body(nif="5402132186", **extra):
    return {"proposerType": "ORGANISATION", "displayName": "Empresa Titular, Lda.", "nif": nif,
            "email": "geral@convite.ao", "phone": "+244923000000", **extra}


def _members(admin_client, proposer_id):
    return admin_client.get(f"/api/v1/members?proposerId={proposer_id}").data["items"]


@pytest.mark.django_db(transaction=True)
def test_organisation_created_with_titular_invites_the_titular(admin_client):
    mail.outbox.clear()
    response = admin_client.post("/api/v1/proposers", _organisation_body(titular=_ORG_TITULAR), format="json")
    assert response.status_code == 201, response.data

    assert [message.to for message in mail.outbox] == [["marta@convite.ao"]]
    titular = next(m for m in _members(admin_client, response.data["id"]) if m["relationshipCode"] == "TITULAR")
    assert titular["firstName"] == "Marta" and titular["attributes"]["phone"] == "+244923111222"
    status = admin_client.get(f"/api/v1/proposers/{response.data['id']}/portal-invitation").data
    assert status["status"] == "SENT" and status["email"] == "marta@convite.ao"


@pytest.mark.django_db(transaction=True)
def test_organisation_without_titular_sends_nothing_and_can_add_it_later(admin_client):
    mail.outbox.clear()
    proposer = admin_client.post("/api/v1/proposers", _organisation_body(), format="json").data
    assert mail.outbox == []
    assert admin_client.get(f"/api/v1/proposers/{proposer['id']}/portal-invitation").data["status"] == "NONE"
    assert admin_client.post(f"/api/v1/proposers/{proposer['id']}/portal-invitation", {}, format="json").status_code == 400

    created = admin_client.post(f"/api/v1/proposers/{proposer['id']}/titular", _ORG_TITULAR, format="json")
    assert created.status_code == 201, created.data
    assert created.data["relationshipCode"] == "TITULAR"
    assert [message.to for message in mail.outbox] == [["marta@convite.ao"]]

    again = admin_client.post(f"/api/v1/proposers/{proposer['id']}/titular",
                              {**_ORG_TITULAR, "email": "outra@convite.ao"}, format="json")
    assert again.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_titular_error_does_not_leave_an_organisation_behind(admin_client):
    body = _organisation_body(titular={**_ORG_TITULAR, "email": "GERAL@convite.ao"})
    assert admin_client.post("/api/v1/proposers", body, format="json").status_code == 400
    assert admin_client.get("/api/v1/proposers?q=Empresa Titular").data["items"] == []


@pytest.mark.django_db
def test_individual_proposer_cannot_carry_an_organisation_titular(admin_client):
    body = {"proposerType": "INDIVIDUAL", "displayName": "Ana", "nif": "023239343LA090", "email": "ana@convite.ao",
            "phone": "+244923000000", "dateOfBirth": "1990-01-01", "titular": _ORG_TITULAR}
    assert admin_client.post("/api/v1/proposers", body, format="json").status_code == 400


@pytest.mark.django_db(transaction=True)
def test_failed_invitation_is_shown_and_resending_sends_the_password_link(admin_client):
    with mock.patch("apps.customer_portal.application.invitation_service.send_portal_invitation_email",
                    side_effect=OSError("servidor indisponível")):
        proposer = _create(admin_client, email="falha@convite.ao", nif="023239343LA090")
    url = f"/api/v1/proposers/{proposer['id']}/portal-invitation"
    assert admin_client.get(url).data["status"] == "FAILED"

    mail.outbox.clear()
    resent = admin_client.post(url, {}, format="json")
    assert resent.status_code == 200, resent.data
    assert resent.data["status"] == "SENT"
    # a conta já ficou ligada ao cliente: o convite continua a levar a definir a palavra-passe
    assert "/recuperar?" in mail.outbox[0].body and "/primeiro?" not in mail.outbox[0].body
