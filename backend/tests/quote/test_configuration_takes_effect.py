"""O que se configura na interface vale nas cotações abertas.

A cotação não tem data de efeito (2026-10-15). Uma cotação aberta (DRAFT/
READY) calcula com o que está em vigor no dia do cálculo: uma tarifa
publicada hoje chega a uma cotação criada ontem. O último cálculo só é
reaproveitado se nada do que entra nele mudou (configurações, plano, pessoas).
Depois de submetida, o prémio fica congelado no dia do último cálculo.
"""
from __future__ import annotations

import datetime
import json

import pytest

import apps.quote.infrastructure.models as quote_models
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.quote.infrastructure.models import Quote
from tests.quote.conftest import set_quote_created_on
from tests.quote.test_business_config_e2e import _publish_all, approver  # noqa: F401  (fixture)
from tests.quote.test_quotes import _member, _plan, _proposer

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)


def _open_quote(client, approver, *, product_code: str) -> dict:  # noqa: F811
    plan_ref = _plan(client, product_code=product_code)
    proposer_id = _proposer(client)
    member_id = _member(client, proposer_id=proposer_id)
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": f"ELIG-{product_code}", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    _publish_all(client, approver, "100000", "2026-01-01")
    quote = client.post("/api/v1/quotes", {"proposerId": proposer_id, "planId": plan_ref["planId"]}, format="json").data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    return {"quote": quote, "memberId": member_id, "planId": plan_ref["planId"]}


@pytest.mark.django_db
def test_a_tariff_published_today_reaches_a_quote_created_yesterday(admin_client, approver, monkeypatch):  # noqa: F811
    scope = _open_quote(admin_client, approver, product_code="TAKES-EFFECT")
    quote_id = scope["quote"]["id"]
    set_quote_created_on(quote_id, YESTERDAY)
    monkeypatch.setattr(quote_models, "pricing_today", lambda: YESTERDAY)
    yesterday = admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    assert yesterday.status_code == 200, yesterday.data
    assert yesterday.data["totalAmount"].startswith("100000")

    # Hoje o GTE publica uma tarifa nova, em vigor a partir de hoje: a versão
    # anterior fica encerrada ontem.
    monkeypatch.setattr(quote_models, "pricing_today", lambda: TODAY)
    _publish_all(admin_client, approver, "120000", TODAY.isoformat())
    today = admin_client.post(f"/api/v1/quotes/{quote_id}/price")  # sem forçar recálculo
    assert today.status_code == 200, today.data
    assert today.data["pricingRunId"] != yesterday.data["pricingRunId"]
    assert today.data["totalAmount"].startswith("120000")


@pytest.mark.django_db
def test_the_last_price_is_reused_only_while_nothing_it_used_changed(admin_client, approver):  # noqa: F811
    scope = _open_quote(admin_client, approver, product_code="REUSE")
    quote_id = scope["quote"]["id"]
    first = admin_client.post(f"/api/v1/quotes/{quote_id}/price").data
    assert admin_client.post(f"/api/v1/quotes/{quote_id}/price").data["pricingRunId"] == first["pricingRunId"]

    # Dados da pessoa corrigidos: novo cálculo.
    member = admin_client.get(f"/api/v1/members/{scope['memberId']}").data
    edited = admin_client.put(
        f"/api/v1/members/{scope['memberId']}",
        {"firstName": "Pessoa", "relationshipCode": "TITULAR", "dateOfBirth": "1980-01-01", "rowVersion": member["rowVersion"]},
        format="json",
    )
    assert edited.status_code == 200, edited.data
    second = admin_client.post(f"/api/v1/quotes/{quote_id}/price").data
    assert second["pricingRunId"] != first["pricingRunId"]

    # Plano alterado na interface: novo cálculo.
    plan = admin_client.get(f"/api/v1/plans/{scope['planId']}").data
    changed = admin_client.patch(
        f"/api/v1/plans/{scope['planId']}", {"name": "Basic (revisto)", "rowVersion": plan["rowVersion"]}, format="json"
    )
    assert changed.status_code == 200, changed.data
    third = admin_client.post(f"/api/v1/quotes/{quote_id}/price").data
    assert third["pricingRunId"] != second["pricingRunId"]
    assert admin_client.post(f"/api/v1/quotes/{quote_id}/price").data["pricingRunId"] == third["pricingRunId"]


@pytest.mark.django_db
def test_a_submitted_quote_keeps_the_day_of_its_last_calculation(admin_client, approver, monkeypatch, tenant):  # noqa: F811
    scope = _open_quote(admin_client, approver, product_code="FROZEN")
    quote_id = scope["quote"]["id"]
    monkeypatch.setattr(quote_models, "pricing_today", lambda: YESTERDAY)
    admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    ready = admin_client.get(f"/api/v1/quotes/{quote_id}").data
    submitted = admin_client.post(f"/api/v1/quotes/{quote_id}/submit", {"rowVersion": ready["rowVersion"]}, format="json")
    assert submitted.status_code == 200, submitted.data

    monkeypatch.setattr(quote_models, "pricing_today", lambda: TODAY)
    token = CurrentActorProvider.bind(Actor(actor_id="test", tenant_id=TenantId(tenant.id), roles=frozenset()))
    try:
        quote = Quote.objects.select_related("latest_pricing_run").get(id=quote_id)
        assert quote.status == "IN_REVIEW" and quote.reference_date == YESTERDAY
    finally:
        CurrentActorProvider.reset(token)
