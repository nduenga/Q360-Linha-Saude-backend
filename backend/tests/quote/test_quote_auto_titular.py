"""Cotação de negócio novo de proponente individual: ao calcular, se a
cotação não tem ninguém, o titular (o próprio proponente) é associado.

Antes, `POST /quotes/{id}/price` falhava com 400 «memberIds tem de conter
pelo menos uma pessoa segura» mesmo com o titular já criado."""
from __future__ import annotations

import json

import pytest

from tests.quote.test_quote_simulator import SETTINGS, _benefit


def _plan(client, *, settings=SETTINGS) -> str:
    """Plano ACTIVE com tarifa publicada (mesma configuração do `_scope`
    do simulador, sem criar proponente nem cotação)."""
    product = client.post("/api/v1/products", {"code": "AT-PROD", "name": "AT"}).data
    plan = client.post(
        "/api/v1/plans",
        {"productId": product["id"], "code": "AT-PLAN", "name": "AT", "settings": settings,
         "complementaryBenefitIds": [_benefit(client, "DENTAL")["id"]]},
        format="json",
    ).data
    client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{_benefit(client, 'HOSPITALIZATION')['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "15000000"}]}},
        format="json",
    )
    params = client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "AT-PARAMS", "effectiveFrom": "2026-01-01",
         "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "100.00"}]},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/pricing-parameter-set/{params['id']}/publish")
    table = client.post(
        "/api/v1/rating-tables",
        {"code": "AT-TABLE", "name": "AT", "effectiveFrom": "2026-01-01", "currencyCode": "AOA",
         "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}]},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rating-table/{table['id']}/publish")
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": "AT-ELIG", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    return plan["id"]


def _individual_proposer(client) -> str:
    resp = client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "Holder", "registrationNumber": "123456789LA042",
         "dateOfBirth": "1990-01-01", "email": "holder@example.com", "phone": "+244900000000"},
        format="json",
    )
    assert resp.status_code in (200, 201), resp.data
    return resp.data["id"]


def _member(client, proposer_id: str, relationship_code: str) -> str:
    resp = client.post(
        "/api/v1/members",
        {"firstName": "Pessoa", "proposerId": proposer_id, "relationshipCode": relationship_code,
         "dateOfBirth": "1990-01-01"},
        format="json",
    )
    assert resp.status_code in (200, 201), resp.data
    return resp.data["id"]


def _quote_members(client, quote_id: str) -> list[dict]:
    return client.get(f"/api/v1/quotes/{quote_id}/members").data["items"]


def _new_quote(client, plan_id, proposer_id) -> str:
    resp = client.post("/api/v1/quotes", {"proposerId": proposer_id, "planId": plan_id}, format="json")
    assert resp.status_code == 201, resp.data
    return resp.data["id"]


@pytest.mark.django_db
def test_pricing_attaches_the_titular_when_the_quote_is_empty(admin_client):
    plan_id = _plan(admin_client)
    proposer_id = _individual_proposer(admin_client)
    titular_id = _member(admin_client, proposer_id, "TITULAR")
    quote_id = _new_quote(admin_client, plan_id, proposer_id)
    assert _quote_members(admin_client, quote_id) == []

    priced = admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    assert priced.status_code == 200, priced.data
    assert [m["memberId"] for m in _quote_members(admin_client, quote_id)] == [titular_id]


@pytest.mark.django_db
def test_explicit_flow_is_unchanged_and_duplicate_is_still_a_conflict(admin_client):
    """Quem já associa o titular à mão antes de calcular não é afectado, e o
    contrato 409 de duplicado mantém-se."""
    plan_id = _plan(admin_client)
    proposer_id = _individual_proposer(admin_client)
    titular_id = _member(admin_client, proposer_id, "TITULAR")
    quote_id = _new_quote(admin_client, plan_id, proposer_id)

    attach = admin_client.post(f"/api/v1/quotes/{quote_id}/members", {"memberId": titular_id}, format="json")
    assert attach.status_code == 200, attach.data
    assert admin_client.post(f"/api/v1/quotes/{quote_id}/members", {"memberId": titular_id}, format="json").status_code == 409

    assert admin_client.post(f"/api/v1/quotes/{quote_id}/price").status_code == 200
    assert [m["memberId"] for m in _quote_members(admin_client, quote_id)] == [titular_id]


@pytest.mark.django_db
def test_only_the_titular_is_attached_not_the_dependents(admin_client):
    plan_id = _plan(admin_client)
    proposer_id = _individual_proposer(admin_client)
    titular_id = _member(admin_client, proposer_id, "TITULAR")
    _member(admin_client, proposer_id, "CONJUGE")
    quote_id = _new_quote(admin_client, plan_id, proposer_id)

    assert admin_client.post(f"/api/v1/quotes/{quote_id}/price").status_code == 200
    assert [m["memberId"] for m in _quote_members(admin_client, quote_id)] == [titular_id]


@pytest.mark.django_db
def test_people_already_on_the_quote_are_never_replaced(admin_client):
    """Se o utilizador escolheu só o cônjuge, o titular não é imposto."""
    plan_id = _plan(admin_client)
    proposer_id = _individual_proposer(admin_client)
    _member(admin_client, proposer_id, "TITULAR")
    spouse_id = _member(admin_client, proposer_id, "CONJUGE")
    quote_id = _new_quote(admin_client, plan_id, proposer_id)
    assert admin_client.post(f"/api/v1/quotes/{quote_id}/members", {"memberId": spouse_id}, format="json").status_code == 200

    admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    assert [m["memberId"] for m in _quote_members(admin_client, quote_id)] == [spouse_id]


@pytest.mark.django_db
def test_no_titular_keeps_the_clear_validation_error(admin_client):
    plan_id = _plan(admin_client)
    proposer_id = _individual_proposer(admin_client)
    quote_id = _new_quote(admin_client, plan_id, proposer_id)

    priced = admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    assert priced.status_code == 400
    assert "pelo menos uma pessoa segura" in priced.data["detail"]
    assert _quote_members(admin_client, quote_id) == []
