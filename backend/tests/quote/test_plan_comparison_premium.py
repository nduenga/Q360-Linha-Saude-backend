"""Comparador de planos com prémio: `POST /plans/compare` tarifa cada plano
com o cálculo real de uma cotação de exemplo e não grava nada."""
from __future__ import annotations

import json

import pytest

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.pricing.infrastructure.models import PricingRun
from apps.quote.infrastructure.models import Quote
from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE
from tests.quote.test_quotes import _plan

URL = "/api/v1/plans/compare"


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


def _second_plan(client, product_id, code):
    benefits = client.get("/api/v1/benefits?category=COMPLEMENTARY&status=ACTIVE&size=200").data["items"]
    body = {"productId": product_id, "code": code, "name": code.title(), "complementaryBenefitIds": [benefits[0]["id"]]}
    created = client.post("/api/v1/plans", body, format="json")
    assert created.status_code == 201, created.data
    return created.data


def _publish(creator, approver, premiums: list[dict]) -> None:
    values = {
        "pricing.reference_premiums": {"currency_code": "AOA", "premiums": premiums},
        "pricing.factors": {"factors": []},
        "pricing.adjustments": {"rules": []},
        "pricing.taxes_fees": {"charges": []},
    }
    for key, value in values.items():
        created = creator.post(BASE, {"configKey": key, "value": value, "effectiveFrom": "2026-01-01"}, format="json")
        assert created.status_code == 201, created.data
        cid = created.data["id"]
        assert creator.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").status_code == 200
        assert approver.post(f"{BASE}/{cid}/approve").data["status"] == "PUBLISHED"


@pytest.fixture
def two_plans(admin_client, approver):
    ref = _plan(admin_client, product_code="COMPARA")
    superior = _second_plan(admin_client, ref["productId"], "SUPERIOR")
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {"code": "ELIG-COMPARA", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    _publish(admin_client, approver, [
        {"age_from": 18, "age_to": 65, "plan": "BASIC", "annual_premium": "100000"},
        {"age_from": 18, "age_to": 65, "plan": "SUPERIOR", "annual_premium": "150000"},
    ])
    return ref["planId"], superior["id"]


def _counts():
    return (Quote.all_tenants.count(), Proposer.all_tenants.count(), InsuredMember.all_tenants.count(),
            PricingRun.all_tenants.count())


def _body(plans, members, **extra):
    return {"planIds": list(plans), "composition": {"members": members, **extra}}


@pytest.mark.django_db
def test_compare_premium_for_a_composition_persists_nothing(admin_client, two_plans):
    basic, superior = two_plans
    before = _counts()
    response = admin_client.post(URL, _body(two_plans, [{"age": 30, "sex": "F"}], paymentFrequency="MENSAL"), format="json")
    assert response.status_code == 200, response.data
    data = response.data
    assert _counts() == before

    pricing = data["pricing"]
    assert pricing["available"] is True and pricing["persisted"] is False
    totals = {r["planId"]: r for r in pricing["results"]}
    assert totals[basic]["totalAmount"].startswith("100000")
    assert totals[superior]["totalAmount"].startswith("150000")
    assert set(totals[basic]["installments"]) == {"MENSAL"}

    premium = next(s for s in data["sections"] if s["key"] == "premium")
    assert [r["key"] for r in premium["rows"]] == ["totalAmount", "installment.MENSAL"]
    total_row = premium["rows"][0]
    assert all(c["state"] == "VALUE" and c["currency"] == "AOA" for c in total_row["cells"])
    assert total_row["different"] is True

    lowest = next(f for f in data["summary"] if f["type"] == "PREMIUM_LOWEST")
    assert lowest["planIds"] == [basic]
    diff = next(f for f in data["summary"] if f["type"] == "PREMIUM_DIFFERENCE")
    assert diff["planIds"] == [superior] and diff["difference"].startswith("50000")


@pytest.mark.django_db
def test_family_composition_adds_each_person(admin_client, two_plans):
    basic, _ = two_plans
    members = [{"age": 40, "relationship": "TITULAR"}, {"age": 38, "sex": "F", "relationship": "CONJUGE"}]
    data = admin_client.post(URL, _body(two_plans, members), format="json").data
    total = next(r for r in data["pricing"]["results"] if r["planId"] == basic)["totalAmount"]
    assert total.startswith("200000")
    premium = next(s for s in data["sections"] if s["key"] == "premium")
    assert {r["key"] for r in premium["rows"]} >= {"totalAmount", "installment.ANUAL", "installment.MENSAL"}


@pytest.mark.django_db
def test_plan_that_cannot_be_priced_does_not_break_the_comparison(admin_client, approver):
    ref = _plan(admin_client, product_code="SEMTARIFA")
    other = _second_plan(admin_client, ref["productId"], "OUTRO")
    response = admin_client.post(URL, _body([ref["planId"], other["id"]], [{"age": 30}]), format="json")
    assert response.status_code == 200, response.data
    data = response.data
    assert data["pricing"]["available"] is False
    assert all(not r["available"] and r["reason"] for r in data["pricing"]["results"])
    cell = next(s for s in data["sections"] if s["key"] == "premium")["rows"][0]["cells"][0]
    assert cell["state"] == "NOT_INFORMED" and cell["reason"]
    assert any(f["type"] == "PREMIUM_UNAVAILABLE" for f in data["summary"])


@pytest.mark.django_db
@pytest.mark.parametrize("composition", [
    {"members": []},
    {"members": [{"age": 130}]},
    {"members": [{"age": 30, "sex": "X"}]},
    {"members": [{"age": 30}], "paymentFrequency": "DIARIO"},
    "texto",
])
def test_invalid_composition_is_rejected(admin_client, two_plans, composition):
    response = admin_client.post(URL, {"planIds": list(two_plans), "composition": composition}, format="json")
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_premium_comparison_needs_quote_calculate(tenant, two_plans):
    reader = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read")
    assert reader.post(URL, _body(two_plans, [{"age": 30}]), format="json").status_code == 403
    # sem prémio, a comparação continua acessível só com leitura
    assert reader.get(f"{URL}?planIds={','.join(two_plans)}").status_code == 200
