"""Os seeders de demonstração (plataforma + portal) criam exactamente os
cenários que o guia de testes promete."""
from __future__ import annotations

import pytest
from django.core import mail
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.customer_portal.management.commands.seed_portal_demo import PORTAL_PASSWORD
from apps.foundation.infrastructure.models import Tenant

BASE = "/api/v1/customer-portal"


@pytest.fixture(autouse=True)
def _no_ip_limit(settings):
    settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP = 0


def _login(tenant, email: str) -> APIClient:
    response = APIClient().post(f"{BASE}/{tenant.id}/auth/login", {"email": email, "password": PORTAL_PASSWORD}, format="json")
    assert response.status_code == 200, response.data
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['accessToken']}")
    return client


def _first_access(tenant, reference: str, document: str):
    return APIClient().post(
        f"{BASE}/{tenant.id}/auth/first-access/request",
        {"reference": reference, "registrationNumber": document}, format="json",
    )


@pytest.mark.django_db(transaction=True)
def test_demo_seeders_create_every_portal_scenario():
    call_command("seed_demo_data")
    tenant = Tenant.objects.get(code="demo-saude")

    # --- Ana: conta com palavra-passe, apólice, atraso, cotação aprovada, pedidos, mensagens
    ana = _login(tenant, "fabioaderio@gmail.com")
    policies = ana.get(f"{BASE}/policies").data["policies"]
    assert [p["status"] for p in policies] == ["ACTIVE"]

    alerts = [a["code"] for a in ana.get(f"{BASE}/dashboard").data["alerts"]]
    assert "PAYMENT_OVERDUE" in alerts

    statuses = {q["status"] for q in ana.get(f"{BASE}/me/quotes").data["quotes"]}
    assert "AWAITING_SIGNATURE" in statuses and "CONTRACTED" in statuses

    requests = ana.get(f"{BASE}/requests").data["requests"]
    assert sorted(r["status"] for r in requests) == ["AWAITING_CUSTOMER", "OPEN"]
    assert ana.get(f"{BASE}/conversations").data["conversations"][0]["unread"] == 1
    codes = {n["code"] for n in ana.get(f"{BASE}/notifications").data["notifications"]}
    assert {"REQUEST_UPDATED", "NEW_MESSAGE", "PAYMENT_OVERDUE", "QUOTE_APPROVED"} <= codes

    # --- Diana: só cotações; o rascunho não aparece
    diana = _login(tenant, "diana.lopes@demo.q360.local")
    assert diana.get(f"{BASE}/policies").data["policies"] == []
    assert {q["status"] for q in diana.get(f"{BASE}/me/quotes").data["quotes"]} == {"IN_REVIEW", "REJECTED"}

    # --- Carlos e Empresa: sem conta -> primeiro acesso, código para o email do registo
    from apps.client.infrastructure.models import Proposer
    from apps.policy.infrastructure.models import Policy

    carlos = Proposer.all_tenants.get(external_reference="DEMO-CARLOS-MENDES")
    carlos_policy = Policy.all_tenants.get(proposer=carlos)
    sent = _first_access(tenant, carlos_policy.policy_number, carlos.registration_number)
    assert sent.status_code == 202, sent.data
    assert mail.outbox[-1].to == [carlos.email]
    assert APIClient().post(f"{BASE}/{tenant.id}/auth/login", {"email": carlos.email, "password": PORTAL_PASSWORD}, format="json").status_code == 401

    empresa = Proposer.all_tenants.get(external_reference="DEMO-EMPRESA-KILAMBA")
    empresa_policy = Policy.all_tenants.get(proposer=empresa, status="ACTIVE")
    assert _first_access(tenant, empresa_policy.policy_number, empresa.registration_number).status_code == 202

    # --- Mariana: sem email no registo
    mariana = Proposer.all_tenants.get(external_reference="DEMO-MARIANA-SEM-EMAIL")
    from apps.quote.infrastructure.models import Quote

    quote = Quote.all_tenants.get(proposer=mariana)
    no_email = _first_access(tenant, quote.quote_number, mariana.registration_number)
    assert no_email.status_code == 409 and no_email.data["code"] == "PORTAL-NO-EMAIL"

    # --- Empresa Kilamba: janela de renovação aberta (testa-se com o primeiro acesso feito)
    code = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    done = APIClient().post(
        f"{BASE}/{tenant.id}/auth/first-access/confirm",
        {"reference": empresa_policy.policy_number, "registrationNumber": empresa.registration_number,
         "otp": code, "password": PORTAL_PASSWORD}, format="json",
    )
    assert done.status_code == 200, done.data
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {done.data['accessToken']}")
    renewal = client.get(f"{BASE}/policies/{empresa_policy.policy_number}/renewal").data
    assert renewal["canRequest"] is True

    # --- idempotência: voltar a correr repõe o estado sem duplicar nada
    call_command("seed_portal_demo")
    assert len(ana.get(f"{BASE}/requests").data["requests"]) == 2
    assert _login(tenant, "fabioaderio@gmail.com")  # a palavra-passe continua válida
    # o seeder repõe a Empresa sem conta, para repetir o primeiro acesso
    assert _first_access(tenant, empresa_policy.policy_number, empresa.registration_number).status_code == 202
