"""Os seeders de demonstração (plataforma + portal) criam exactamente os
cenários que o guia de testes promete."""
from __future__ import annotations

import pytest
from django.core import mail
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from apps.customer_portal.management.commands.prepare_portal_test_accounts import TEST_EMAILS
from apps.customer_portal.management.commands.seed_portal_demo import PORTAL_PASSWORD
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.management.commands.seed_demo_data import demo_email

BASE = "/api/v1/customer-portal"


@pytest.fixture(autouse=True)
def _no_ip_limit(settings):
    settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP = 0
    settings.DEBUG = True


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
    ana_client = _login(tenant, demo_email("ANA"))
    policies = ana_client.get(f"{BASE}/policies").data["policies"]
    assert [p["status"] for p in policies] == ["ACTIVE"]

    alerts = [a["code"] for a in ana_client.get(f"{BASE}/dashboard").data["alerts"]]
    assert "PAYMENT_OVERDUE" in alerts
    # a prestação em atraso é de um período que já começou, dentro da vigência
    import datetime

    payments = ana_client.get(f"{BASE}/payments").data["installments"]
    overdue = [i for i in payments if i["status"] == "OVERDUE"]
    today, start = datetime.date.today().isoformat(), str(policies[0]["startDate"])
    assert overdue and all(str(i["periodFrom"]) <= today for i in overdue)
    assert all(str(i["dueDate"]) >= start for i in payments)

    statuses = {q["status"] for q in ana_client.get(f"{BASE}/me/quotes").data["quotes"]}
    assert "AWAITING_SIGNATURE" in statuses and "CONTRACTED" in statuses

    requests = ana_client.get(f"{BASE}/requests").data["requests"]
    assert sorted(r["status"] for r in requests) == ["AWAITING_CUSTOMER", "OPEN"]
    assert ana_client.get(f"{BASE}/conversations").data["conversations"][0]["unread"] == 1
    codes = {n["code"] for n in ana_client.get(f"{BASE}/notifications").data["notifications"]}
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
    assert carlos.email == demo_email("CARLOS")
    assert APIClient().post(f"{BASE}/{tenant.id}/auth/login", {"email": carlos.email, "password": PORTAL_PASSWORD}, format="json").status_code == 401

    ana_proposer = Proposer.all_tenants.get(external_reference="DEMO-ANA-SILVA")
    ana_policy = Policy.all_tenants.get(proposer=ana_proposer, status="ACTIVE")
    ana_first_access = _first_access(tenant, ana_policy.policy_number, ana_proposer.registration_number)
    assert ana_first_access.status_code == 202, ana_first_access.data
    assert mail.outbox[-1].to == [demo_email("ANA")]

    empresa = Proposer.all_tenants.get(external_reference="DEMO-EMPRESA-KILAMBA")
    empresa_policy = Policy.all_tenants.get(proposer=empresa, status="ACTIVE")
    company_first_access = _first_access(tenant, empresa_policy.policy_number, empresa.registration_number)
    assert company_first_access.status_code == 202, company_first_access.data
    assert mail.outbox[-1].to == ["empresa.kilamba@demo.q360.local"]
    # por omissão o seed nunca usa caixas de correio reais
    assert {carlos.email, ana_proposer.email} == {"carlos.mendes@demo.q360.local", "ana.silva@demo.q360.local"}

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
    assert len(ana_client.get(f"{BASE}/requests").data["requests"]) == 2
    assert _login(tenant, demo_email("ANA"))  # a palavra-passe continua válida
    # o seeder repõe a Empresa sem conta, para repetir o primeiro acesso
    assert _first_access(tenant, empresa_policy.policy_number, empresa.registration_number).status_code == 202


@pytest.mark.django_db(transaction=True)
def test_production_preparation_is_explicit_idempotent_and_preserves_passwords(settings, monkeypatch):
    # Quem testa com caixas reais escolhe-as explicitamente.
    monkeypatch.setenv("Q360_DEMO_EMAIL_ANA", TEST_EMAILS[0])
    monkeypatch.setenv("Q360_DEMO_EMAIL_CARLOS", TEST_EMAILS[1])
    settings.DEBUG = False
    with pytest.raises(CommandError, match="ambientes DEBUG"):
        call_command("seed_demo_data")
    with pytest.raises(CommandError, match="ambientes DEBUG"):
        call_command("seed_portal_demo")
    settings.DEBUG = True

    call_command("seed_demo_data")
    tenant = Tenant.objects.get(code="demo-saude")
    existing_passwords = dict(
        CustomerAccount.all_tenants.filter(tenant_id=tenant.id).values_list("email", "password_hash")
    )

    with pytest.raises(CommandError, match="--confirm-production"):
        call_command("prepare_portal_test_accounts", tenant_id=str(tenant.id))

    call_command(
        "prepare_portal_test_accounts",
        tenant_id=str(tenant.id),
        confirm_production=True,
    )
    accounts = {
        account.email: account
        for account in CustomerAccount.all_tenants.filter(tenant_id=tenant.id, email__in=TEST_EMAILS)
    }
    assert set(accounts) == set(TEST_EMAILS)
    assert all(
        CustomerAccountProposer.all_tenants.filter(
            tenant_id=tenant.id,
            customer_account=account,
        ).exists()
        for account in accounts.values()
    )
    assert {
        email: account.password_hash
        for email, account in accounts.items()
        if email in existing_passwords
    } == {
        email: password_hash
        for email, password_hash in existing_passwords.items()
        if email in TEST_EMAILS
    }

    links_before = CustomerAccountProposer.all_tenants.filter(
        tenant_id=tenant.id,
        customer_account__email__in=TEST_EMAILS,
    ).count()
    call_command(
        "prepare_portal_test_accounts",
        tenant_id=str(tenant.id),
        confirm_production=True,
    )
    assert CustomerAccountProposer.all_tenants.filter(
        tenant_id=tenant.id,
        customer_account__email__in=TEST_EMAILS,
    ).count() == links_before
