"""R7 — simular o impacto de uma versão antes de a publicar e parâmetros
globais do sistema (operacionais editáveis pelo GTE vs estruturais)."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_quote_simulator import _quote, _runs, _scope, _total

REASON = "Revisão trimestral das tarifas"


def _draft_params(client, *, base, extra=()):
    return client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "SIM-PARAMS", "effectiveFrom": "2026-01-01",
         "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": base},
                        {"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "10"}, *extra]},
        format="json",
    ).data


def _simulate(client, kind, config_id, **body):
    return client.post(f"/api/v1/configuration/{kind}/{config_id}/impact-simulation", body, format="json")


# ------------------------------------------------------------- impact simulation
@pytest.mark.django_db
def test_impact_of_a_draft_parameter_set_before_publishing(admin_client):
    scope = _scope(admin_client)  # 2 pessoas, prémio base 100 -> 200.00
    draft = _draft_params(admin_client, base="150.00")
    runs = _runs(admin_client)

    result = _simulate(admin_client, "pricing-parameter-set", draft["id"])
    assert result.status_code == 200, result.data
    data = result.data
    assert data["candidate"]["versionNo"] == 2 and data["candidate"]["status"] == "DRAFT"
    assert data["sampled"] == 1 and data["compared"] == 1 and data["skipped"] == []
    assert data["totals"] == {"before": "200.00", "after": "300.00", "delta": "100.00", "deltaPercent": "50.00"}
    assert data["deltaPercent"] == {"average": "50.00", "max": "50.00", "min": "50.00"}
    assert data["mostAffected"][0]["quoteId"] == scope["quoteId"] and data["mostAffected"][0]["delta"] == "100.00"

    # nada mudou: o rascunho continua rascunho, a cotação e os cálculos também
    assert _runs(admin_client) == runs
    assert _total(admin_client, scope) == Decimal("200.00")
    versions = admin_client.get(f"/api/v1/configuration/pricing-parameter-set/{draft['id']}/versions").data
    assert [v["status"] for v in versions] == ["DRAFT", "PUBLISHED"]


@pytest.mark.django_db
def test_impact_of_a_draft_rating_table_and_a_pricing_rule(admin_client):
    _scope(admin_client)
    table = admin_client.post(
        "/api/v1/rating-tables",
        {"code": "SIM-TABLE", "name": "v2", "effectiveFrom": "2026-01-01", "currencyCode": "AOA",
         "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.10"}]},
        format="json",
    ).data
    assert _simulate(admin_client, "rating-table", table["id"]).data["totals"]["deltaPercent"] == "10.00"

    rule = admin_client.post(
        "/api/v1/rule-versions",
        {"code": "SIM-PRICING-RULE", "name": "r", "ruleDomain": "PRICING", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({"adjustments": [{"code": "FLAT", "when": {}, "amount": "5.00"}]})},
        format="json",
    ).data
    result = _simulate(admin_client, "rule-version", rule["id"]).data
    assert result["totals"] == {"before": "200.00", "after": "210.00", "delta": "10.00", "deltaPercent": "5.00"}


@pytest.mark.django_db
def test_impact_ignores_quotes_priced_with_another_code_and_unsupported_types(admin_client):
    _scope(admin_client)
    other = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "OTHER-PARAMS", "effectiveFrom": "2026-01-01", "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "999.00"}]},
        format="json",
    ).data
    result = _simulate(admin_client, "pricing-parameter-set", other["id"]).data
    assert result["compared"] == 0 and result["skipped"][0]["reason"] == "OTHER_CONFIGURATION_CODE"
    assert result["totals"]["deltaPercent"] is None

    eligibility = admin_client.post(
        "/api/v1/rule-versions",
        {"code": "SIM-ELIG-2", "name": "e", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": "{}"},
        format="json",
    ).data
    assert _simulate(admin_client, "rule-version", eligibility["id"]).status_code == 400
    assert _simulate(admin_client, "pricing-parameter-set", other["id"], limit=0).status_code == 400


@pytest.mark.django_db
def test_impact_needs_pricing_config_permission(admin_client, tenant):
    _scope(admin_client)
    draft = _draft_params(admin_client, base="150.00")
    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write")
    assert _simulate(subscriber, "pricing-parameter-set", draft["id"]).status_code == 403


# ------------------------------------------------------------ system parameters
@pytest.mark.django_db
def test_parameters_separate_operational_from_structural(admin_client):
    items = {p["code"]: p for p in admin_client.get("/api/v1/system-parameters").data}
    assert items["quote.validity_days"]["category"] == "OPERATIONAL" and items["quote.validity_days"]["editable"] is True
    assert items["quote.validity_days"]["value"] == 30 and items["quote.validity_days"]["isDefault"] is True
    for code in ("pricing.rounding_policy", "pricing.formula", "capital.pro_rata_rule"):
        assert items[code]["category"] == "STRUCTURAL" and items[code]["editable"] is False
    assert items["capital.pro_rata_rule"]["value"] is False  # PDF: não há regra de rateio
    structural = admin_client.get("/api/v1/system-parameters?category=STRUCTURAL").data
    assert {p["code"] for p in structural} == {"pricing.rounding_policy", "pricing.formula", "capital.pro_rata_rule"}


@pytest.mark.django_db
def test_set_a_parameter_with_reason_history_and_optimistic_locking(admin_client):
    url = "/api/v1/system-parameters/quote.validity_days"
    assert admin_client.put(url, {"value": 45, "rowVersion": 0, "reason": "x"}, format="json").status_code == 400
    updated = admin_client.put(url, {"value": 45, "rowVersion": 0, "reason": REASON}, format="json")
    assert updated.status_code == 200, updated.data
    assert updated.data["value"] == 45 and updated.data["isDefault"] is False and updated.data["rowVersion"] == 0
    second = admin_client.put(url, {"value": 60, "rowVersion": 0, "reason": REASON}, format="json")
    assert second.status_code == 200 and second.data["value"] == 60 and second.data["rowVersion"] == 1
    stale = admin_client.put(url, {"value": 90, "rowVersion": 0, "reason": REASON}, format="json")
    assert stale.status_code == 409 and stale.data["code"] == "VERSION-CONFLICT"
    current = admin_client.get(url).data
    assert current["value"] == 60


@pytest.mark.django_db
def test_validation_of_parameter_values_and_unknown_codes(admin_client):
    url = "/api/v1/system-parameters/quote.validity_days"
    for bad in (0, 366, "30", 3.5, True, None):
        assert admin_client.put(url, {"value": bad, "rowVersion": 0, "reason": REASON}, format="json").status_code == 400, bad
    pct = "/api/v1/system-parameters/renewal.default_medical_inflation_pct"
    assert admin_client.put(pct, {"value": "12.50", "rowVersion": 0, "reason": REASON}, format="json").data["value"] == "12.5"
    for bad in ("-1", "abc", 5.5, "1001"):
        assert admin_client.put(pct, {"value": bad, "rowVersion": 1, "reason": REASON}, format="json").status_code == 400, bad
    assert admin_client.get("/api/v1/system-parameters/nope.code").status_code == 404
    assert admin_client.put("/api/v1/system-parameters/nope.code", {"value": 1, "rowVersion": 0, "reason": REASON}, format="json").status_code == 404


@pytest.mark.django_db
def test_structural_parameters_cannot_be_changed_by_the_gte(admin_client):
    resp = admin_client.put(
        "/api/v1/system-parameters/pricing.rounding_policy", {"value": "OTHER", "rowVersion": 0, "reason": REASON}, format="json"
    )
    assert resp.status_code == 403 and resp.data["code"] == "SEC-403" and "structural" in resp.data["detail"]
    assert admin_client.put(
        "/api/v1/system-parameters/capital.pro_rata_rule", {"value": True, "rowVersion": 0, "reason": REASON}, format="json"
    ).status_code == 403


@pytest.mark.django_db
def test_parameter_revisions_and_rollback(admin_client):
    url = "/api/v1/system-parameters/quote.validity_days"
    admin_client.put(url, {"value": 45, "rowVersion": 0, "reason": "Primeira alteração do prazo"}, format="json")
    admin_client.put(url, {"value": 60, "rowVersion": 0, "reason": "Segunda alteração do prazo"}, format="json")
    revisions = admin_client.get(f"{url}/revisions").data
    assert [(r["revisionNo"], r["value"], r["action"]) for r in revisions] == [(2, 60, "UPDATED"), (1, 45, "UPDATED")]
    assert revisions[0]["reason"] == "Segunda alteração do prazo" and revisions[0]["changedBy"]

    assert admin_client.post(f"{url}/rollback", {"revisionNo": 1, "reason": "x"}, format="json").status_code == 400
    assert admin_client.post(f"{url}/rollback", {"revisionNo": 9, "reason": REASON}, format="json").status_code == 404
    restored = admin_client.post(f"{url}/rollback", {"revisionNo": 1, "reason": "Voltar ao prazo anterior"}, format="json")
    assert restored.status_code == 200 and restored.data["value"] == 45
    after = admin_client.get(f"{url}/revisions").data
    assert [r["revisionNo"] for r in after] == [3, 2, 1] and after[0]["action"] == "ROLLBACK_TO_1"


@pytest.mark.django_db
def test_validity_days_parameter_drives_new_quotes(admin_client):
    scope = _scope(admin_client)
    assert _quote(admin_client, scope)["validUntil"] == "2026-07-01"  # 30 dias (env) até o GTE alterar
    admin_client.put("/api/v1/system-parameters/quote.validity_days", {"value": 10, "rowVersion": 0, "reason": REASON}, format="json")
    created = admin_client.post(
        "/api/v1/quotes", {"proposerId": scope["proposerId"], "planId": scope["planId"], "effectiveDate": "2026-06-01"}, format="json"
    )
    assert created.data["validUntil"] == "2026-06-11"

