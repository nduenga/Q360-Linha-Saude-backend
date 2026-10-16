"""Catálogo único de variáveis (`/business-config/formulas/variables`): motor,
parâmetros e auxiliares das fórmulas publicadas, campos do produto e campos
das regras, cada um com onde pode ser usado. E o catálogo do motor visto pelo
fornecedor (`/platform/formula-engine`), sem tenant."""
from __future__ import annotations

import pytest

from tests.quote.test_business_config_e2e import approver  # noqa: F401  (fixture)
from tests.quote.test_formula_config_e2e import FORMULAS, VALUE
from tests.quote.test_platform_parameters import _platform_client, _platform_key  # noqa: F401  (fixture)
from tests.quote.test_product_pricing_setup import SETUP, _publish_setup
from tests.quote.test_quotes import _plan

URL = f"{FORMULAS}/variables"


def _by_token(data, source):
    return {v["token"]: v for v in data["variables"] if v["source"] == source}


@pytest.mark.django_db
def test_catalog_joins_engine_formulas_product_and_rule_fields(admin_client, approver):  # noqa: F811
    empty = admin_client.get(URL).data
    assert set(_by_token(empty, "SYSTEM")) == {"person_amount", "person_base", "age", "members_count",
                                               "total_amount", "base_total"}
    assert empty["sources"]["pricingFormulas"] is None and not _by_token(empty, "PARAMETER")
    assert {f["name"] for f in empty["functions"]} == {"min", "max", "abs", "round", "tabela"}
    assert "total_premium" in _by_token(empty, "RULE_FIELD")

    created = admin_client.post(FORMULAS, {"value": VALUE, "effectiveFrom": "2026-01-01"}, format="json").data
    admin_client.post(f"{FORMULAS}/{created['id']}/submit")
    assert approver.post(f"{FORMULAS}/{created['id']}/approve").status_code == 200
    product_id = _plan(admin_client, product_code="VARS")["productId"]
    _publish_setup(admin_client, approver, product_id, SETUP)

    data = admin_client.get(URL, {"productId": product_id}).data
    assert data["sources"]["pricingFormulas"]["versionNo"] == 1
    assert data["sources"]["productSetup"]["status"] == "PUBLISHED"
    parameter = _by_token(data, "PARAMETER")["taxa_gestao"]
    assert parameter["value"] == "0.10" and parameter["label"] == "Taxa de gestão"
    assert _by_token(data, "AUXILIARY")["gestao"]["usableIn"] == ["PRICING_FORMULAS:QUOTE"]
    assert {"actividade", "multiplicador"} <= set(_by_token(data, "PRODUCT_GROUP"))
    assert "actividade__comercio" in _by_token(data, "PRODUCT_OPTION")
    assert _by_token(data, "PRODUCT_FIELD")["massa_salarial"]["unit"] == "AOA"
    assert "premio_anual" in _by_token(data, "PRODUCT_FORMULA")
    assert set(_by_token(data, "PRODUCT_SYSTEM")) == {"premio_tecnico", "pessoas"}

    person = admin_client.get(URL, {"usableIn": "PRICING_FORMULAS:PERSON"}).data
    assert "age" in _by_token(person, "SYSTEM") and "total_amount" not in _by_token(person, "SYSTEM")
    assert "taxa_gestao" in _by_token(person, "PARAMETER") and not _by_token(person, "RULE_FIELD")
    assert admin_client.get(URL, {"productId": "nao-e-uuid"}).status_code == 400


@pytest.mark.django_db
def test_platform_sees_the_engine_catalog_without_a_tenant(admin_client):
    platform = _platform_client("engine@q360.test")
    engine = platform.get("/api/v1/platform/formula-engine")
    assert engine.status_code == 200, engine.data
    assert {f["name"] for f in engine.data["pricingFormulas"]["functions"]} == {"min", "max", "abs", "round", "tabela"}
    assert {s["key"] for s in engine.data["rules"]["stages"]} >= {"ELIGIBILITY", "VALIDATION", "WORKFLOW"}
    assert engine.data["limits"]["maxExpressionLength"] == 500
    assert admin_client.get("/api/v1/platform/formula-engine").status_code in (401, 403)
