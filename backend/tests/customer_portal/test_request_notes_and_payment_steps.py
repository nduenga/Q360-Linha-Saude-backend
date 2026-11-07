"""Atendimento (cap. 16) e portal (cap. 18): nota interna nunca chega ao
cliente, resposta + estado numa só ação, e próximo passo com instruções de pagamento."""
from __future__ import annotations

import datetime

import pytest

from apps.business_config.infrastructure.models import BusinessConfiguration
from tests.customer_portal.test_portal_requests_api import BASE, _ask, _customer
from tests.customer_portal.test_self_service_api import _set_quote


@pytest.mark.django_db
def test_internal_note_stays_with_the_team_and_reply_goes_with_the_status(admin_client, tenant):
    _, client = _customer(admin_client, tenant, "APO-N-001", "901111111LA011")
    number = _ask(client, "DOCUMENT_COPY", description="Segunda via").data["requestNumber"]

    noted = admin_client.post(f"/api/v1/portal-requests/{number}/notes", {"note": "Cliente ligou; confirmar morada."}, format="json")
    assert noted.status_code == 200, noted.data
    assert noted.data["history"][-1]["internal"] is True
    assert noted.data["timeline"][-1]["kind"] == "INTERNAL_NOTE"
    assert admin_client.post(f"/api/v1/portal-requests/{number}/notes", {"note": "  "}, format="json").status_code == 400

    moved = admin_client.post(
        f"/api/v1/portal-requests/{number}/transition",
        {"toStatus": "IN_REVIEW", "message": "Estamos a tratar do seu pedido."}, format="json",
    )
    assert moved.status_code == 200, moved.data
    kinds = [item["kind"] for item in moved.data["timeline"]]
    assert "MESSAGE" in kinds and kinds.count("INTERNAL_NOTE") == 1

    seen = client.get(f"{BASE}/requests/{number}").data
    assert all("confirmar morada" not in (event["note"] or "") for event in seen["history"])
    assert all("internal" not in event for event in seen["history"])
    thread = client.get(f"{BASE}/messages?contextType=REQUEST&contextRef={number}").data
    assert any(m["body"] == "Estamos a tratar do seu pedido." for m in thread["messages"])


@pytest.mark.django_db
def test_failed_transition_does_not_send_the_reply(admin_client, tenant):
    _, client = _customer(admin_client, tenant, "APO-N-002", "902222222LA022")
    number = _ask(client, "DOCUMENT_COPY", description="Segunda via").data["requestNumber"]
    refused = admin_client.post(
        f"/api/v1/portal-requests/{number}/transition",
        {"toStatus": "COMPLETED", "message": "Concluído."}, format="json",
    )
    assert refused.status_code == 409
    thread = client.get(f"{BASE}/messages?contextType=REQUEST&contextRef={number}").data
    assert thread["messages"] == []


@pytest.mark.django_db
def test_accepted_quote_shows_the_next_step_and_how_to_pay(admin_client, tenant):
    scope, client = _customer(admin_client, tenant, "APO-N-003", "903333333LA033")
    _set_quote(scope, status="APPROVED", valid_until=datetime.date.today() + datetime.timedelta(days=5))
    quote_number = "Q-APO-N-003"

    before = client.get(f"{BASE}/me/quotes/{quote_number}").data
    assert before["accepted"] is False and before["nextStep"]["code"] == "ACCEPT"
    assert before["paymentInstructions"] is None

    BusinessConfiguration.all_tenants.create(
        tenant_id=tenant.id, config_key="portal.payment_instructions", version_no=1, status="PUBLISHED",
        value_json={"enabled": True, "bank_name": "Banco Exemplo", "account_holder": "Seguradora Exemplo",
                    "iban": "AO06000000000000000000000", "reference_rule": "QUOTE_NUMBER"},
        effective_from=datetime.date(2020, 1, 1), created_by="test",
    )
    assert _ask(client, "ACCEPT_QUOTE", quoteNumber=quote_number).status_code == 201
    after = client.get(f"{BASE}/me/quotes/{quote_number}").data
    assert after["accepted"] is True and after["nextStep"]["code"] == "AWAITING_ISSUANCE"
    assert after["paymentInstructions"]["iban"] == "AO06000000000000000000000"
    assert "número da cotação" in after["paymentInstructions"]["reference"]
    assert client.get(f"{BASE}/payments").data["paymentInstructions"]["bankName"] == "Banco Exemplo"
