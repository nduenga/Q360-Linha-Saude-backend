"""Configuração de negócio de ponta a ponta: tarifa criada pela interface
(DRAFT), aprovada por outro utilizador, usada numa cotação e reprecificada
depois de uma nova versão publicada. Nenhum valor comercial vem do código."""
from __future__ import annotations

import json

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_quotes import _member, _plan, _proposer

SCOPE = "q360.read q360.write q360.admin q360.approve"
BASE = "/api/v1/business-config/configurations"


def _values(premium: str) -> dict[str, dict]:
    return {
        "pricing.reference_premiums": {
            "currency_code": "AOA",
            "premiums": [{"age_from": 18, "age_to": 65, "plan": "BASIC", "annual_premium": premium}],
        },
        "pricing.factors": {"factors": []},
        "pricing.adjustments": {"rules": []},
        "pricing.taxes_fees": {"charges": []},
    }


def _publish_all(creator, approver, premium: str, effective_from: str) -> None:
    for key, value in _values(premium).items():
        created = creator.post(BASE, {"configKey": key, "value": value, "effectiveFrom": effective_from}, format="json")
        assert created.status_code == 201, created.data
        cid = created.data["id"]
        assert creator.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").status_code == 200
        approved = approver.post(f"{BASE}/{cid}/approve")
        assert approved.status_code == 200, approved.data
        assert approved.data["status"] == "PUBLISHED"


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


@pytest.mark.django_db
def test_catalog_lists_form_schemas(admin_client):
    items = admin_client.get("/api/v1/business-config/catalog").data["items"]
    keys = {i["key"] for i in items}
    assert {"pricing.reference_premiums", "product.plans", "security.approval_rules"} <= keys
    assert all(i["formSchema"]["sections"] for i in items)


@pytest.mark.django_db
def test_creator_cannot_approve_own_configuration(admin_client):
    value = _values("100000")["pricing.reference_premiums"]
    cid = admin_client.post(BASE, {"configKey": "pricing.reference_premiums", "value": value,
                                   "effectiveFrom": "2026-01-01"}, format="json").data["id"]
    admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json")
    response = admin_client.post(f"{BASE}/{cid}/approve")
    assert response.status_code == 403
    assert response.data["code"] == "SEC-403"


@pytest.mark.django_db
def test_only_draft_is_editable_and_row_version_is_checked(admin_client):
    value = _values("100000")["pricing.reference_premiums"]
    created = admin_client.post(BASE, {"configKey": "pricing.reference_premiums", "value": value,
                                       "effectiveFrom": "2026-01-01"}, format="json").data
    stale = admin_client.put(f"{BASE}/{created['id']}", {"value": value, "rowVersion": 99}, format="json")
    assert stale.status_code == 409 and stale.data["code"] == "VERSION-CONFLICT"
    ok = admin_client.put(f"{BASE}/{created['id']}", {"value": value, "rowVersion": 0}, format="json")
    assert ok.status_code == 200 and ok.data["rowVersion"] == 1
    admin_client.post(f"{BASE}/{created['id']}", {"action": "submit"}, format="json")
    locked = admin_client.put(f"{BASE}/{created['id']}", {"value": value}, format="json")
    assert locked.status_code == 409


@pytest.mark.django_db
def test_read_only_actor_cannot_write(tenant):
    reader = make_client(tenant_id=tenant.id, roles=["AUDITOR"], scope="q360.read q360.audit")
    assert reader.get(BASE).status_code == 200
    denied = reader.post(BASE, {"configKey": "pricing.factors", "value": {}, "effectiveFrom": "2026-01-01"}, format="json")
    assert denied.status_code == 403


@pytest.mark.django_db
def test_tariff_change_reprices_quote_and_records_versions(admin_client, approver):
    plan_ref = _plan(admin_client, product_code="BC-E2E")
    proposer_id = _proposer(admin_client)
    member_id = _member(admin_client, proposer_id=proposer_id)
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {"code": "ELIG-BC", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")

    # Sem configuração publicada nem tabelas legadas: falha explícita, sem valores inventados.
    quote = admin_client.post(
        "/api/v1/quotes",
        {"proposerId": proposer_id, "planId": plan_ref["planId"], "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    assert admin_client.post(f"/api/v1/quotes/{quote['id']}/price").status_code == 422

    _publish_all(admin_client, approver, "100000", "2026-01-01")
    first = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert first.status_code == 200, first.data
    run_one = first.data
    assert run_one["currencyCode"] == "AOA"
    assert run_one["totalAmount"].startswith("100000")
    versions = run_one["versions"]["businessConfigurationVersions"]
    assert set(versions) == set(_values("1"))
    assert all(v["versionNo"] == 1 and v["checksum"] for v in versions.values())

    # Sem alteração de configuração reutiliza o cálculo.
    again = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert again.data["pricingRunId"] == run_one["pricingRunId"]

    # Nova versão publicada: o cálculo anterior é considerado desatualizado.
    _publish_all(admin_client, approver, "120000", "2026-02-01")
    second = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert second.status_code == 200, second.data
    assert second.data["pricingRunId"] != run_one["pricingRunId"]
    assert second.data["totalAmount"].startswith("120000")
    assert all(v["versionNo"] == 2 for v in second.data["versions"]["businessConfigurationVersions"].values())

    # A versão anterior foi encerrada na véspera da nova vigência.
    listed = admin_client.get(BASE, {"configKey": "pricing.reference_premiums"}).data["items"]
    old = next(i for i in listed if i["version"] == 1)
    assert old["effectiveTo"] == "2026-01-31"
