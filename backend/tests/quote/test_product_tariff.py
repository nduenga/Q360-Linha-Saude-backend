"""Tarifa de um produto por passo do cálculo e simulação de rascunhos: a
simulação usa o cálculo real de uma cotação de exemplo e não grava nada."""
from __future__ import annotations

import json

import pytest

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.pricing.infrastructure.models import PricingRun
from apps.quote.infrastructure.models import Quote
from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE, _publish_all, _values
from tests.quote.test_quotes import _plan


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


def _product(client, approver) -> dict:
    ref = _plan(client, product_code="TARIFA")
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": "ELIG-TARIFA", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    _publish_all(client, approver, "100000", "2026-01-01")
    return ref


def _counts():
    return (Quote.all_tenants.count(), Proposer.all_tenants.count(), InsuredMember.all_tenants.count(),
            PricingRun.all_tenants.count())


@pytest.mark.django_db
def test_tariff_lists_the_steps_in_engine_order_with_owner_and_versions(admin_client, approver):
    ref = _product(admin_client, approver)
    tariff = admin_client.get(f"/api/v1/products/{ref['productId']}/tariff")
    assert tariff.status_code == 200, tariff.data
    data = tariff.data
    assert data["engine"]["owner"] == "CODE" and data["engine"]["order"][0] == "PURE_PREMIUM"
    assert [p["code"] for p in data["plans"]] == ["BASIC"]
    stages = {s["code"]: s for s in data["stages"]}
    assert stages["LEGAL_TAXES"]["owner"] == "PLATFORM" and stages["LEGAL_TAXES"]["editable"] is False
    assert {p["code"]: p["value"] for p in stages["LEGAL_TAXES"]["platformParameters"]} == {
        "tax.arseg_levy_pct": "1", "tax.stamp_duty_pct": "0"}
    premium = next(c for c in stages["PURE_PREMIUM"]["configurations"] if c["configKey"] == "pricing.reference_premiums")
    assert premium["published"]["versionNo"] == 1 and premium["draft"] is None
    assert stages["PURE_PREMIUM"]["summary"] == {"source": "REFERENCE_PREMIUMS", "rows": 1}
    assert stages["PRODUCT_SETUP"]["scope"] == "PRODUCT" and stages["RISK_FACTORS"]["scope"] == "TENANT"
    assert admin_client.get("/api/v1/products/00000000-0000-0000-0000-000000000000/tariff").status_code == 404


@pytest.mark.django_db
def test_simulation_runs_the_real_calculation_with_drafts_and_persists_nothing(admin_client, approver):
    ref = _product(admin_client, approver)
    url = f"/api/v1/products/{ref['productId']}/tariff/simulate"
    body = {"planId": ref["planId"], "members": [{"age": 30, "sex": "F"}], "paymentFrequency": "TRIMESTRAL"}
    before = _counts()
    published = admin_client.post(url, body, format="json")
    assert published.status_code == 200, published.data
    assert published.data["totalAmount"].startswith("100000") and published.data["persisted"] is False
    assert published.data["installments"] == {"TRIMESTRAL": "25000.00"}
    assert published.data["appliedDrafts"] == []
    assert {c["owner"] for c in published.data["components"]} <= {"TENANT", "PLATFORM", "CODE"}
    assert any(s["stepCode"] == "CONTEXT_RESOLVED" and s["owner"] == "CODE" for s in published.data["steps"])
    assert _counts() == before  # nem cotação, nem pessoas, nem cálculo ficaram gravados

    draft = admin_client.post(BASE, {"configKey": "pricing.reference_premiums",
                                     "value": _values("120000")["pricing.reference_premiums"],
                                     "effectiveFrom": "2026-11-01"}, format="json").data
    with_draft = admin_client.post(url, {**body, "configurationIds": [draft["id"]]}, format="json").data
    assert with_draft["totalAmount"].startswith("120000")
    assert [d["configurationId"] for d in with_draft["appliedDrafts"]] == [draft["id"]]
    assert admin_client.post(url, {**body, "includeOpenDrafts": True}, format="json").data["totalAmount"].startswith("120000")
    assert admin_client.post(url, body, format="json").data["totalAmount"].startswith("100000")

    # O rascunho continua rascunho, com a vigência que tinha.
    after = admin_client.get(f"{BASE}/{draft['id']}").data
    assert after["status"] == "DRAFT" and after["effectiveFrom"] == "2026-11-01"
    assert _counts() == before


@pytest.mark.django_db
def test_simulation_rejects_foreign_plans_and_drafts(admin_client, approver):
    ref = _product(admin_client, approver)
    other = _plan(admin_client, product_code="OUTRO")
    url = f"/api/v1/products/{ref['productId']}/tariff/simulate"
    assert admin_client.post(url, {"planId": other["planId"], "members": [{"age": 30}]},
                             format="json").status_code == 400
    assert admin_client.post(url, {"planId": ref["planId"], "members": []}, format="json").status_code == 400
    foreign = admin_client.post(BASE, {"configKey": "group.rules", "value": {}, "effectiveFrom": "2026-01-01"},
                                format="json")
    if foreign.status_code == 201:
        refused = admin_client.post(url, {"planId": ref["planId"], "members": [{"age": 30}],
                                          "configurationIds": [foreign.data["id"]]}, format="json")
        assert refused.status_code == 400 and "não são da tarifa" in refused.data["detail"]
