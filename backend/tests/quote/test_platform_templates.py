"""Modelos de partida do fornecedor: carga inicial a partir do código,
versões com aprovação por outra conta, e adoção pelo tenant como rascunhos
(cópia, nunca ligação)."""
from __future__ import annotations

import io

import pytest
from django.core.management import call_command

from tests.quote.test_business_config_e2e import BASE
from tests.quote.test_platform_parameters import REASON, _platform_client, _platform_key  # noqa: F401  (fixture)

PLATFORM = "/api/v1/platform/templates"
FORMULAS = {"parameters": [{"code": "minimo", "value": "50000"}],
            "rules": [{"code": "premio_minimo", "name": "Prémio mínimo por pessoa", "order": 1,
                       "expression": "max(total_amount, minimo * members_count)"}]}


def _seed() -> str:
    out = io.StringIO()
    call_command("seed_platform_templates", stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_seed_publishes_the_initial_templates_once_and_tenants_adopt_them_as_drafts(admin_client):
    assert "publicado" in _seed() and "já existe" in _seed()
    listed = {t["code"]: t for t in admin_client.get("/api/v1/templates").data}
    assert set(listed) == {"saude-angola-referencia", "modelo-actuarial-sau-sag"}
    assert listed["modelo-actuarial-sau-sag"]["configKeys"] == ["pricing.actuarial_model"]
    assert listed["saude-angola-referencia"]["marketProducts"] is True and "rules.custom" in listed["saude-angola-referencia"]["configKeys"]
    detail = admin_client.get("/api/v1/templates/modelo-actuarial-sau-sag").data
    assert "assumptions" in detail["content"]["configurations"]["pricing.actuarial_model"]

    adopted = admin_client.post("/api/v1/templates/modelo-actuarial-sau-sag/adopt", {"effectiveFrom": "2026-11-01"},
                                format="json")
    assert adopted.status_code == 201, adopted.data
    draft = adopted.data["createdDrafts"][0]
    assert draft["configKey"] == "pricing.actuarial_model" and draft["status"] == "DRAFT"
    stored = admin_client.get(f"{BASE}/{draft['configurationId']}").data
    assert stored["metadata"]["adoptedFromTemplate"] == {"code": "modelo-actuarial-sau-sag", "versionNo": 1}
    assert admin_client.get("/api/v1/templates/nao-existe").status_code == 404


@pytest.mark.django_db
def test_product_template_creates_drafts_and_market_products(admin_client):
    _seed()
    adopted = admin_client.post("/api/v1/templates/saude-angola-referencia/adopt", {}, format="json")
    assert adopted.status_code == 201, adopted.data
    keys = {d["configKey"] for d in adopted.data["createdDrafts"]}
    assert {"product.plans", "product.coverages", "rules.custom", "pricing.taxes_fees"} <= keys
    assert all(d["status"] == "DRAFT" for d in adopted.data["createdDrafts"])
    assert adopted.data["marketProducts"]["createdProducts"]
    assert admin_client.get("/api/v1/products").status_code == 200


@pytest.mark.django_db
def test_platform_manages_template_versions_with_two_accounts(admin_client):
    maker = _platform_client("maker@q360.test")
    checker = _platform_client("checker@q360.test")
    body = {"code": "formulas-minimo", "kind": "FORMULA_SET", "name": "Prémio mínimo por pessoa",
            "content": {"configurations": {"pricing.formulas": FORMULAS}}, "reason": REASON}
    wrong_key = maker.post(PLATFORM, {**body, "content": {"configurations": {"rules.custom": {"rules": []}}}},
                           format="json")
    assert wrong_key.status_code == 400 and "FORMULA_SET" in str(wrong_key.data)
    invalid = maker.post(PLATFORM, {**body, "content": {"configurations": {"pricing.formulas": {"rules": [
        {"code": "x", "name": "x", "expression": "1 +"}]}}}}, format="json")
    assert invalid.status_code == 400
    proposed = maker.post(PLATFORM, body, format="json")
    assert proposed.status_code == 201 and proposed.data["status"] == "PENDING_APPROVAL"
    assert admin_client.get("/api/v1/templates").data == []  # pendente não aparece aos tenants
    assert maker.post(f"{PLATFORM}/formulas-minimo/versions/1/approve", {}, format="json").status_code == 403
    assert checker.post(f"{PLATFORM}/formulas-minimo/versions/1/approve", {}, format="json").status_code == 200
    assert [t["code"] for t in admin_client.get("/api/v1/templates").data] == ["formulas-minimo"]

    change_kind = maker.post(PLATFORM, {**body, "kind": "PRODUCT"}, format="json")
    assert change_kind.status_code == 400 and "mudar de tipo" in str(change_kind.data)
    assert admin_client.post(PLATFORM, body, format="json").status_code in (401, 403)

    adopted = admin_client.post("/api/v1/templates/formulas-minimo/adopt", {}, format="json").data
    # Uma versão nova do modelo não mexe no que o tenant já adotou.
    maker.post(PLATFORM, {**body, "content": {"configurations": {"pricing.formulas": {**FORMULAS, "parameters": [
        {"code": "minimo", "value": "70000"}]}}}}, format="json")
    checker.post(f"{PLATFORM}/formulas-minimo/versions/2/approve", {}, format="json")
    kept = admin_client.get(f"{BASE}/{adopted['createdDrafts'][0]['configurationId']}").data
    assert kept["value"]["parameters"][0]["value"] == "50000"
    history = maker.get(f"{PLATFORM}/formulas-minimo/versions").data
    assert [(v["versionNo"], v["isLatestPublished"]) for v in history] == [(2, True), (1, False)]
