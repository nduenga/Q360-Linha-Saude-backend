"""Dados de mercado, constantes e tabelas de referência do fornecedor nas
fórmulas dos tenants: `cambio_usd_aoa` e `tabela("codigo", chave, "coluna")`.
Mudar o valor no fornecedor (com aprovação) muda o preço das cotações que
o usam, com a versão registada no rasto."""
from __future__ import annotations

import pytest

from tests.quote.test_formula_config_e2e import FORMULAS, _priced_quote, approver  # noqa: F401  (fixture)
from tests.quote.test_platform_parameters import LAW, REASON, _platform_client, _platform_key, _publish  # noqa: F401

TABLES = "/api/v1/platform/reference-tables"
TABLE = {
    "code": "fatores_teste", "name": "Fatores por número de pessoas", "keyColumn": "pessoas",
    "columns": [{"code": "pessoas", "type": "NUMBER"}, {"code": "fator", "type": "NUMBER", "label": "Fator"}],
    "rows": [{"pessoas": 1, "fator": "1.5"}, {"pessoas": 2, "fator": "1,4"}],
    "source": "Tabela de teste", "reason": REASON,
}


@pytest.fixture
def maker(db):
    return _platform_client("maker@q360.test")


@pytest.fixture
def checker(db):
    return _platform_client("checker@q360.test")


def _publish_table(maker, checker, body=TABLE):
    proposed = maker.post(TABLES, body, format="json")
    assert proposed.status_code == 201, proposed.data
    assert maker.post(f"{TABLES}/{body['code']}/versions/{proposed.data['versionNo']}/approve", {},
                      format="json").status_code == 403
    approved = checker.post(f"{TABLES}/{body['code']}/versions/{proposed.data['versionNo']}/approve", {}, format="json")
    assert approved.status_code == 200, approved.data
    return approved.data


def _publish_formulas(client, approver, value):  # noqa: F811
    created = client.post(FORMULAS, {"value": value, "effectiveFrom": "2026-01-01"}, format="json")
    assert created.status_code == 201, created.data
    client.post(f"{FORMULAS}/{created.data['id']}/submit")
    assert approver.post(f"{FORMULAS}/{created.data['id']}/approve").status_code == 200


@pytest.mark.django_db
def test_reference_tables_are_validated_versioned_and_readable_by_tenants(maker, checker, admin_client):
    bad = maker.post(TABLES, {**TABLE, "rows": [{"pessoas": 1, "fator": "x"}]}, format="json")
    assert bad.status_code == 400 and "não é um número" in bad.data["detail"]
    dup = maker.post(TABLES, {**TABLE, "rows": [{"pessoas": 1, "fator": 1}, {"pessoas": "1.0", "fator": 2}]}, format="json")
    assert dup.status_code == 400 and "repetida" in dup.data["detail"]
    assert maker.post(TABLES, {**TABLE, "keyColumn": "outra"}, format="json").status_code == 400
    assert admin_client.get("/api/v1/reference-tables").data == []

    published = _publish_table(maker, checker)
    assert published["status"] == "PUBLISHED" and published["rowCount"] == 2
    listed = admin_client.get("/api/v1/reference-tables").data
    assert [t["code"] for t in listed] == ["fatores_teste"] and "rows" not in listed[0]
    detail = admin_client.get("/api/v1/reference-tables/fatores_teste").data
    assert detail["rows"] == [{"pessoas": "1", "fator": "1.5"}, {"pessoas": "2", "fator": "1.4"}]
    assert admin_client.get("/api/v1/reference-tables/nao_existe").status_code == 404
    assert admin_client.post(TABLES, TABLE, format="json").status_code in (401, 403)
    platform_list = maker.get(TABLES).data
    assert platform_list[0]["inEffect"]["versionNo"] == 1 and platform_list[0]["pendingVersions"] == []


@pytest.mark.django_db
def test_formulas_use_the_provider_exchange_rate_and_reprice_when_it_changes(maker, checker, admin_client, approver):  # noqa: F811
    quote, before = _priced_quote(admin_client, approver)
    assert before["totalAmount"] == "100000.00"
    _publish_formulas(admin_client, approver, {"rules": [
        {"code": "evacuacao", "name": "Evacuação em dólares", "expression": "total_amount + 10 * cambio_usd_aoa", "order": 1},
    ]})
    first = admin_client.post(f"/api/v1/quotes/{quote['id']}/price").data
    assert first["totalAmount"] == "109312.70"  # 100 000 + 10 × 931,27 (valor inicial do Excel)

    _publish(maker, checker, "market.usd_aoa", {"value": "1000"})
    second = admin_client.post(f"/api/v1/quotes/{quote['id']}/price").data
    assert second["pricingRunId"] != first["pricingRunId"] and second["totalAmount"] == "110000.00"
    steps = admin_client.get(f"/api/v1/pricing/{second['pricingRunId']}/explanation").data["steps"]
    context = next(s for s in steps if s["stepCode"] == "CONTEXT_RESOLVED")
    assert context["output"]["platformParameterVersions"]["market.usd_aoa"] == 1
    formula_step = next(s for s in steps if s["ruleCode"] == "evacuacao")
    assert "1000" in str(formula_step["input"])  # o valor da constante usado fica no rasto


@pytest.mark.django_db
def test_formulas_read_reference_tables_and_constant_names_are_reserved(maker, checker, admin_client, approver):  # noqa: F811
    quote, _ = _priced_quote(admin_client, approver)
    reserved = admin_client.post(FORMULAS, {"value": {"parameters": [{"code": "cambio_usd_aoa", "value": "1"}],
                                                      "rules": []}, "effectiveFrom": "2026-01-01"}, format="json")
    assert reserved.status_code == 400 and "reservado" in str(reserved.data)

    _publish_table(maker, checker)
    _publish_formulas(admin_client, approver, {"rules": [
        {"code": "fator_grupo", "name": "Fator por pessoas", "order": 1,
         "expression": 'total_amount * tabela("fatores_teste", members_count, "fator")'},
    ]})
    priced = admin_client.post(f"/api/v1/quotes/{quote['id']}/price").data
    assert priced["totalAmount"] == "150000.00"

    test = admin_client.post(f"{FORMULAS}/test", {"expression": 'tabela("fatores_teste", 2, "fator") * cambio_usd_aoa',
                                                  "variables": {}}, format="json").data
    assert test["valid"] is True and test["result"] == "1303.778"
    assert [s["operation"] for s in test["steps"]] == ["tabela", "CONSTANT", "*"]
    missing = admin_client.post(f"{FORMULAS}/test", {"expression": 'tabela("fatores_teste", 9, "fator")'}, format="json")
    assert missing.status_code == 400 and "não tem a chave" in missing.data["error"]

    catalog = admin_client.get(f"{FORMULAS}/variables").data
    constants = {v["token"]: v for v in catalog["variables"] if v["source"] == "PLATFORM_CONSTANT"}
    assert constants["cambio_usd_aoa"]["value"] == "931.27" and constants["taxa_arseg_pct"]["readOnly"] is True
    assert catalog["referenceTables"][0]["example"] == 'tabela("fatores_teste", chave, "fator")'
