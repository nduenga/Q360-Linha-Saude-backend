"""Ao registar um proponente com email, o cliente recebe o link do Portal do
Cliente e consegue criar a palavra-passe sem ter ainda apólice nem cotação."""
from __future__ import annotations

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer

BASE = "/api/v1/customer-portal"


@pytest.fixture(autouse=True)
def _no_ip_limit(settings):
    settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP = 0
    settings.CUSTOMER_PORTAL_URL = "https://portal.exemplo.ao/portal-cliente"


def _create(admin_client, *, email, nif, kind="ORGANISATION"):
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
    proposer = _create(admin_client, email="rh@convite.ao", nif="5417000001")

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
    first = _create(admin_client, email="mediador@convite.ao", nif="5417000003")
    second = _create(admin_client, email="mediador@convite.ao", nif="5417000004")
    account = CustomerAccount.all_tenants.get(tenant_id=tenant.id, email="mediador@convite.ao")
    linked = set(CustomerAccountProposer.all_tenants.filter(customer_account=account).values_list("proposer_id", flat=True))
    assert {str(x) for x in linked} == {first["id"]}
    assert "Primeiro acesso" in mail.outbox[-1].body and "/primeiro?" in mail.outbox[-1].body
    assert second["id"] not in {str(x) for x in linked}


def test_no_email_no_invitation():
    """Sem email não há convite (p.ex. proponente criado na cotação sem email)."""
    from types import SimpleNamespace

    from apps.customer_portal.application.invitation_service import invite_proposer

    assert invite_proposer(SimpleNamespace(email="", display_name="X", id="p1")) is None
