"""Configuração em cascata seguradora → produto → plano: a versão do produto
(`<chave>@<produto>`) substitui a geral só nesse produto; dentro dela, a
linha do plano prevalece sobre a linha sem plano."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest

from apps.business_config.application.overlays import apply_coverage_overlay, effective_plan_settings
from apps.business_config.application.readers import BusinessSnapshot
from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE, _publish, _publish_all, _values
from tests.quote.test_quotes import _member, _plan, _proposer


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


def _eligibility_rules(client, rules: dict) -> None:
    created = client.post(
        "/api/v1/rule-versions",
        {"code": f"ELIG-{uuid.uuid4().hex[:6]}", "name": "Eligibility", "ruleDomain": "ELIGIBILITY",
         "effectiveFrom": "2026-01-01", "artifactType": "JSON", "artifactRef": json.dumps(rules)},
        format="json",
    ).data
    assert client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish").status_code == 200


def _priced_quote(client, plan_id: str, *, registration: str, email: str) -> dict:
    proposer_id = _proposer(client, registration_number=registration, email=email)
    member_id = _member(client, proposer_id=proposer_id)
    quote = client.post("/api/v1/quotes", {"proposerId": proposer_id, "planId": plan_id}, format="json").data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    priced = client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert priced.status_code == 200, priced.data
    return {**priced.data, "quoteId": quote["id"]}


@pytest.mark.django_db
def test_product_tariff_replaces_the_general_one_only_in_that_product(admin_client, approver):
    product_a = _plan(admin_client, product_code="CASC-A")
    product_b = _plan(admin_client, product_code="CASC-B")
    _eligibility_rules(admin_client, {})
    _publish_all(admin_client, approver, "100000", "2026-01-01")
    _publish(admin_client, approver, f"pricing.reference_premiums@{product_a['productId']}",
             _values("150000")["pricing.reference_premiums"])

    in_a = _priced_quote(admin_client, product_a["planId"], registration="123456789LA042", email="a@demo.q360.local")
    in_b = _priced_quote(admin_client, product_b["planId"], registration="123456789LA043", email="b@demo.q360.local")
    assert in_a["totalAmount"].startswith("150000")
    assert in_b["totalAmount"].startswith("100000")
    used_a = in_a["versions"]["businessConfigurationVersions"]
    assert used_a["pricing.reference_premiums"]["configKey"] == f"pricing.reference_premiums@{product_a['productId']}"
    assert used_a["pricing.reference_premiums"]["scope"] == "PRODUCT"
    assert used_a["pricing.factors"]["scope"] == "TENANT"  # o resto herda a geral
    assert in_b["versions"]["businessConfigurationVersions"]["pricing.reference_premiums"]["scope"] == "TENANT"


@pytest.mark.django_db
def test_minimum_premium_of_the_product_with_plan_override(admin_client, approver):
    ref = _plan(admin_client, product_code="CASC-MIN")
    _eligibility_rules(admin_client, {})
    _publish_all(admin_client, approver, "100000", "2026-01-01")
    key = f"product.minimum_premium@{ref['productId']}"
    _publish(admin_client, approver, key, {"items": [{"annual_minimum": "200000"}]})

    priced = _priced_quote(admin_client, ref["planId"], registration="123456789LA042", email="m@demo.q360.local")
    assert priced["totalAmount"].startswith("200000")
    minimum = next(c for c in priced["components"] if c["code"] == "MINIMUM_PREMIUM")
    assert minimum["adjustmentAmount"].startswith("100000")
    assert priced["versions"]["businessConfigurationVersions"]["product.minimum_premium"]["scope"] == "PRODUCT"

    # A linha do plano prevalece sobre a linha sem plano; o mínimo por pessoa conta também.
    _publish(admin_client, approver, key, {"items": [
        {"annual_minimum": "200000"},
        {"plan": "BASIC", "annual_minimum": "90000", "per_person_minimum": "130000"},
    ]}, effective_from="2026-02-01")
    again = admin_client.post(f"/api/v1/quotes/{priced['quoteId']}/price")
    assert again.status_code == 200, again.data
    assert again.data["totalAmount"].startswith("130000")

    # Acima do mínimo não há componente de prémio mínimo.
    _publish(admin_client, approver, key, {"items": [{"plan": "BASIC", "annual_minimum": "50000"}]},
             effective_from="2026-03-01")
    above = admin_client.post(f"/api/v1/quotes/{priced['quoteId']}/price").data
    assert above["totalAmount"].startswith("100000")
    assert not any(c["code"] == "MINIMUM_PREMIUM" for c in above["components"])


@pytest.mark.django_db
def test_minimum_premium_requires_an_amount_and_one_row_per_plan(admin_client):
    bad = admin_client.post(BASE, {"configKey": "product.minimum_premium", "value": {"items": [{"plan": "BASIC"}]},
                                   "effectiveFrom": "2026-01-01"}, format="json")
    assert bad.status_code == 400
    repeated = admin_client.post(BASE, {"configKey": "product.minimum_premium", "value": {"items": [
        {"annual_minimum": "1"}, {"annual_minimum": "2"}]}, "effectiveFrom": "2026-01-01"}, format="json")
    assert repeated.status_code == 400


@pytest.mark.django_db
def test_only_scopable_keys_of_existing_products_accept_a_product_version(admin_client):
    ref = _plan(admin_client, product_code="CASC-KEYS")

    def create(key: str):
        return admin_client.post(BASE, {"configKey": key, "value": {"charges": []}, "effectiveFrom": "2026-01-01"},
                                 format="json")

    assert create(f"pricing.taxes_fees@{ref['productId']}").status_code == 400  # encargos ficam sempre gerais
    assert create(f"pricing.taxes_fees@{uuid.uuid4()}").status_code == 400
    assert create("pricing.factors@nao-e-um-produto").status_code == 400
    ok = admin_client.post(BASE, {"configKey": f"pricing.factors@{ref['productId']}", "value": {"factors": []},
                                  "effectiveFrom": "2026-01-01"}, format="json")
    assert ok.status_code == 201, ok.data


@pytest.mark.django_db
def test_product_configuration_shows_origin_and_copies_drafts(admin_client, approver):
    product_a = _plan(admin_client, product_code="CASC-COPY-A")
    product_b = _plan(admin_client, product_code="CASC-COPY-B")
    _publish_all(admin_client, approver, "100000", "2026-01-01")
    url = f"/api/v1/products/{product_a['productId']}/configuration"

    described = admin_client.get(url)
    assert described.status_code == 200, described.data
    items = {i["configKey"]: i for i in described.data["items"]}
    assert items["pricing.reference_premiums"]["source"] == "GENERAL"
    assert items["product.waiting_periods"]["source"] == "NONE"
    assert "pricing.taxes_fees" not in items
    assert "pricing.taxes_fees" in {i["configKey"] for i in described.data["generalOnly"]}
    plan_field = next(f for f in items["product.waiting_periods"]["formSchema"]["sections"][0]["fields"]
                      if f["name"] == "plan")
    assert plan_field["options"] == ["BASIC"]

    copied = admin_client.post(f"{url}/copy", {"source": "GENERAL"}, format="json")
    assert copied.status_code == 201, copied.data
    created = {c["configKey"]: c for c in copied.data["created"]}
    assert set(created) == {"pricing.reference_premiums", "pricing.factors", "pricing.adjustments"}
    assert created["pricing.factors"]["copiedFrom"] == "pricing.factors"
    assert {s["configKey"] for s in copied.data["skipped"]} >= {"product.waiting_periods"}
    draft = admin_client.get(f"{BASE}/{created['pricing.reference_premiums']['configurationId']}").data
    assert draft["status"] == "DRAFT" and draft["configKey"].endswith(product_a["productId"])

    # Uma segunda cópia não mexe nos rascunhos já abertos.
    again = admin_client.post(f"{url}/copy", {"source": "GENERAL", "configKeys": ["pricing.factors"]}, format="json")
    assert again.data["created"] == [] and again.data["skipped"][0]["configKey"] == "pricing.factors"

    # Publicado, o produto passa a usar a sua versão; a fila de aprovações diz de que produto é.
    cid = created["pricing.reference_premiums"]["configurationId"]
    admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json")
    pending = admin_client.get("/api/v1/business-config/approvals/pending").data["items"]
    assert any(p["label"] == "Prémios de referência · produto CASC-COPY-A" for p in pending)
    assert approver.post(f"{BASE}/{cid}/approve").status_code == 200
    items = {i["configKey"]: i for i in admin_client.get(url).data["items"]}
    assert items["pricing.reference_premiums"]["source"] == "PRODUCT"
    assert items["pricing.reference_premiums"]["generalChangedSinceCopy"] is None
    assert items["pricing.factors"]["generalChangedSinceCopy"] is None  # o produto ainda usa a geral

    # A geral muda depois da cópia: o produto não recebe a alteração e o ecrã é avisado.
    _publish(admin_client, approver, "pricing.reference_premiums", _values("120000")["pricing.reference_premiums"])
    items = {i["configKey"]: i for i in admin_client.get(url).data["items"]}
    assert items["pricing.reference_premiums"]["generalChangedSinceCopy"] == {"copiedVersionNo": 1, "generalVersionNo": 2}

    # Copiar de outro produto: leva o que vale nele (a versão dele ou a geral).
    from_a = admin_client.post(f"/api/v1/products/{product_b['productId']}/configuration/copy",
                               {"source": "PRODUCT", "sourceProductId": product_a["productId"],
                                "configKeys": ["pricing.reference_premiums", "pricing.adjustments"]}, format="json")
    assert from_a.status_code == 201, from_a.data
    origins = {c["configKey"]: c["copiedFrom"] for c in from_a.data["created"]}
    assert origins == {"pricing.reference_premiums": f"pricing.reference_premiums@{product_a['productId']}",
                       "pricing.adjustments": "pricing.adjustments"}
    same = admin_client.post(f"{url}/copy", {"source": "PRODUCT", "sourceProductId": product_a["productId"]},
                             format="json")
    assert same.status_code == 400


@pytest.mark.django_db
def test_entry_ages_of_the_product_and_plan_prevail_over_the_general_rule(admin_client, approver):
    ref = _plan(admin_client, product_code="CASC-AGE")
    _eligibility_rules(admin_client, {"minEntryAge": 18})
    proposer_id = _proposer(admin_client)
    child = _member(admin_client, proposer_id=proposer_id, date_of_birth="2020-01-01")

    def decision() -> str:
        response = admin_client.post("/api/v1/eligibility/evaluate", {
            "proposerId": proposer_id, "memberId": child, "planId": ref["planId"],
            "effectiveDate": "2026-06-01", "context": {}}, format="json")
        assert response.status_code == 200, response.data
        return response.data["decision"]

    assert decision() == "HARD_STOP"
    key = f"product.age_limits@{ref['productId']}"
    _publish(admin_client, approver, key, {"items": [{"entry_min_age": 0, "entry_max_age": 64}]})
    assert decision() == "ELIGIBLE"
    _publish(admin_client, approver, key, {"items": [{"entry_min_age": 0}, {"plan": "BASIC", "entry_min_age": 10}]},
             effective_from="2026-02-01")
    assert decision() == "HARD_STOP"


def _fake_plan(code: str, product_id: str):
    return SimpleNamespace(code=code, name=code, settings_json={"segment": "INDIVIDUAL_FAMILY"}, product_id=product_id)


def test_waiting_periods_cascade_from_general_to_product_to_plan():
    product_id = str(uuid.uuid4())
    snapshot = BusinessSnapshot(values={
        "product.waiting_periods": {"items": [{"coverage": "HOSPITALIZATION", "individual_days": 30}]},
        f"product.waiting_periods@{product_id}": {"items": [
            {"coverage": "HOSPITALIZATION", "individual_days": 90},
            {"plan": "PREMIUM", "coverage": "HOSPITALIZATION", "individual_days": 0},
        ]},
    })

    def waiting(plan) -> dict:
        out, warnings = apply_coverage_overlay(
            plan=plan, settings=plan.settings_json,
            coverages={"HOSPITALIZATION": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "1000"}]}},
            benefits={"HOSPITALIZATION": ("Internamento", "BASE", {})}, snapshot=snapshot,
        )
        assert warnings == []
        return out["HOSPITALIZATION"]["waitingDays"]

    assert waiting(_fake_plan("BASIC", product_id)) == {"individual": 90}
    assert waiting(_fake_plan("PREMIUM", product_id)) == {"individual": 0}
    assert waiting(_fake_plan("BASIC", str(uuid.uuid4()))) == {"individual": 30}  # outro produto herda a geral


def test_age_limits_cascade_into_plan_settings():
    product_id = str(uuid.uuid4())
    snapshot = BusinessSnapshot(values={
        "product.age_limits": {"items": [{"entry_max_age": 60, "renewal_max_age": 70}]},
        f"product.age_limits@{product_id}": {"items": [
            {"entry_min_age": 0, "entry_max_age": 64},
            {"plan": "PREMIUM", "entry_max_age": 55},
        ]},
    })
    basic = effective_plan_settings(_fake_plan("BASIC", product_id), snapshot=snapshot)
    premium = effective_plan_settings(_fake_plan("PREMIUM", product_id), snapshot=snapshot)
    other = effective_plan_settings(_fake_plan("BASIC", str(uuid.uuid4())), snapshot=snapshot)
    assert basic["entryAge"] == {"min": 0, "max": 64} and "permanenceAge" not in basic
    assert premium["entryAge"] == {"min": 0, "max": 55}
    assert other["entryAge"] == {"min": 0, "max": 60} and other["permanenceAge"] == {"max": 70}
