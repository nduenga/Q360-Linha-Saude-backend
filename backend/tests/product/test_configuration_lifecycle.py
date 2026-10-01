"""R7 — o GTE altera parâmetros técnicos/tarifários sem fornecedor: histórico,
diferenças entre versões e reverter (nova versão, motivo, auditoria)."""
from __future__ import annotations

import json

import pytest

from tests.pricing.test_plan_pricing import _member, _plan, _body, NO_OPTIONS

REASON = "Reverter por erro de tarifa detetado"


def _publish(client, kind, config_id):
    resp = client.post(f"/api/v1/configuration/{kind}/{config_id}/publish")
    assert resp.status_code == 200, resp.data
    return resp.data


def _table(client, *, code="HIST-TABLE", age_factor="1.00", publish=True, effective_from="2026-01-01"):
    created = client.post(
        "/api/v1/rating-tables",
        {"code": code, "name": code, "effectiveFrom": effective_from, "currencyCode": "AOA",
         "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": age_factor}]},
        format="json",
    ).data
    return _publish(client, "rating-table", created["id"]) if publish else created


def _params(client, *, code="HIST-PARAMS", base="100.00", publish=True, extra=()):
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": code, "effectiveFrom": "2026-01-01",
         "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": base}, *extra]},
        format="json",
    ).data
    return _publish(client, "pricing-parameter-set", created["id"]) if publish else created


def _rule(client, *, code="HIST-RULE", adjustments=(), publish=True):
    created = client.post(
        "/api/v1/rule-versions",
        {"code": code, "name": code, "ruleDomain": "PRICING", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({"adjustments": list(adjustments)})},
        format="json",
    ).data
    return _publish(client, "rule-version", created["id"]) if publish else created


def _total(client, plan_id, member):
    resp = client.post("/api/v1/pricing/calculate", _body(plan_id, member, table="HIST-TABLE", params="HIST-PARAMS"), format="json")
    assert resp.status_code == 200, resp.data
    return resp.data["totalAmount"]


# -------------------------------------------------------------- rating tables
@pytest.mark.django_db
def test_history_lists_every_version_of_the_same_code(admin_client):
    v1 = _table(admin_client)
    v2 = _table(admin_client, age_factor="2.00")
    history = admin_client.get(f"/api/v1/configuration/rating-table/{v2['id']}/versions").data
    assert [(h["versionNo"], h["status"]) for h in history] == [(2, "PUBLISHED"), (1, "PUBLISHED")]
    assert history[0]["publishedBy"] and history[0]["publishedAt"]
    other = _table(admin_client, code="OTHER-TABLE")
    assert [h["versionNo"] for h in admin_client.get(f"/api/v1/configuration/rating-table/{other['id']}/versions").data] == [1]
    assert v1["id"] in [h["id"] for h in history]


@pytest.mark.django_db
def test_rollback_to_a_still_published_version_retires_the_newer_ones(admin_client):
    _params(admin_client)
    v1 = _table(admin_client)
    v2 = _table(admin_client, age_factor="2.00")
    plan_id = _plan(admin_client, settings=NO_OPTIONS)
    member = _member(admin_client)
    assert _total(admin_client, plan_id, member) == "200.00"  # a v2 (fator 2.00) está em vigor

    short = admin_client.post(f"/api/v1/configuration/rating-table/{v1['id']}/rollback", {"reason": "x"}, format="json")
    assert short.status_code == 400
    result = admin_client.post(f"/api/v1/configuration/rating-table/{v1['id']}/rollback", {"reason": REASON}, format="json")
    assert result.status_code == 200, result.data
    assert result.data["current"]["id"] == v1["id"] and result.data["current"]["versionNo"] == 1
    assert [r["id"] for r in result.data["retired"]] == [v2["id"]]
    assert _total(admin_client, plan_id, member) == "100.00"  # o preço voltou ao que era

    history = admin_client.get(f"/api/v1/configuration/rating-table/{v1['id']}/versions").data
    assert [(h["versionNo"], h["status"]) for h in history] == [(2, "RETIRED"), (1, "PUBLISHED")]


@pytest.mark.django_db
def test_rollback_to_a_retired_version_publishes_a_new_copy_of_it(admin_client):
    _params(admin_client)
    v1 = _table(admin_client)
    v2 = _table(admin_client, age_factor="2.00")
    admin_client.post(f"/api/v1/configuration/rating-table/{v1['id']}/retire")  # v1 saiu de uso
    plan_id = _plan(admin_client, settings=NO_OPTIONS)
    member = _member(admin_client)
    assert _total(admin_client, plan_id, member) == "200.00"

    result = admin_client.post(f"/api/v1/configuration/rating-table/{v1['id']}/rollback", {"reason": REASON}, format="json")
    assert result.status_code == 200, result.data
    current = result.data["current"]
    assert current["versionNo"] == 3 and current["status"] == "PUBLISHED" and current["id"] not in (v1["id"], v2["id"])
    assert result.data["restoredFrom"]["id"] == v1["id"]
    assert _total(admin_client, plan_id, member) == "100.00"
    history = admin_client.get(f"/api/v1/configuration/rating-table/{v1['id']}/versions").data
    assert [(h["versionNo"], h["status"]) for h in history] == [(3, "PUBLISHED"), (2, "RETIRED"), (1, "RETIRED")]
    # o histórico nunca é reescrito: v1 e v2 continuam lá com o conteúdo original
    diff = admin_client.get(f"/api/v1/configuration/rating-table/{v1['id']}/diff?against={current['id']}").data
    assert diff["changes"] == []


@pytest.mark.django_db
def test_rollback_rules(admin_client):
    v1 = _table(admin_client)
    only = admin_client.post(f"/api/v1/configuration/rating-table/{v1['id']}/rollback", {"reason": REASON}, format="json")
    assert only.status_code == 409  # já é a versão em vigor

    draft = _table(admin_client, age_factor="3.00", publish=False)
    assert admin_client.post(f"/api/v1/configuration/rating-table/{draft['id']}/rollback", {"reason": REASON}, format="json").status_code == 409
    import uuid

    assert admin_client.post(f"/api/v1/configuration/rating-table/{uuid.uuid4()}/rollback", {"reason": REASON}, format="json").status_code == 404
    assert admin_client.post(f"/api/v1/configuration/bogus/{v1['id']}/rollback", {"reason": REASON}, format="json").status_code == 404


@pytest.mark.django_db
def test_rollback_needs_pricing_config_permission(admin_client, tenant):
    from tests.product.conftest import make_client

    v1 = _table(admin_client)
    _table(admin_client, age_factor="2.00")
    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write")
    assert subscriber.post(f"/api/v1/configuration/rating-table/{v1['id']}/rollback", {"reason": REASON}, format="json").status_code == 403
    assert subscriber.get(f"/api/v1/configuration/rating-table/{v1['id']}/versions").status_code == 200


@pytest.mark.django_db
def test_rollback_is_audited_with_reason_before_and_after(admin_client, tenant):
    from tests.product.conftest import make_client

    v1 = _table(admin_client)
    v2 = _table(admin_client, age_factor="2.00")
    admin_client.post(f"/api/v1/configuration/rating-table/{v1['id']}/rollback", {"reason": REASON}, format="json")
    auditor = make_client(tenant_id=tenant.id, roles=["AUDITOR"], scope="q360.read q360.audit")
    events = auditor.get("/api/v1/audit-events?action=configuration.rolled_back").data["items"]
    metadata = events[0]["metadata"]
    assert metadata["reason"] == REASON and metadata["configType"] == "rating-table" and metadata["restoredFromVersionNo"] == 1
    assert metadata["before"]["retired"][0]["id"] == v2["id"] and metadata["after"]["current"]["id"] == v1["id"]


# --------------------------------------------------------------- diff
@pytest.mark.django_db
def test_rating_table_diff_added_removed_changed(admin_client):
    v1 = _table(admin_client)
    created = admin_client.post(
        "/api/v1/rating-tables",
        {"code": "HIST-TABLE", "name": "v2", "effectiveFrom": "2026-01-01", "currencyCode": "AOA",
         "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.50"},
                     {"factorCode": "TIER_FACTOR", "dimensions": {"tier": "MEDIUM"}, "factorValue": "1.20"}]},
        format="json",
    ).data
    diff = admin_client.get(f"/api/v1/configuration/rating-table/{v1['id']}/diff?against={created['id']}").data
    by_kind = {}
    for change in diff["changes"]:
        by_kind.setdefault(change["kind"], []).append(change)
    assert diff["from"]["versionNo"] == 1 and diff["to"]["versionNo"] == 2
    assert len(by_kind["ADDED"]) == 1 and by_kind["ADDED"][0]["after"]["factorCode"] == "TIER_FACTOR"
    # o fator 1.00 e o 1.50 têm a mesma identidade (código+dimensões+prioridade) -> alterado
    assert len(by_kind["CHANGED"]) == 1 and by_kind["CHANGED"][0]["before"]["factorValue"] == "1" and by_kind["CHANGED"][0]["after"]["factorValue"] == "1.5"
    assert "REMOVED" not in by_kind
    assert admin_client.get(f"/api/v1/configuration/rating-table/{v1['id']}/diff").status_code == 400
    other = _table(admin_client, code="OTHER-CODE")
    assert admin_client.get(f"/api/v1/configuration/rating-table/{v1['id']}/diff?against={other['id']}").status_code == 409


# ------------------------------------------------------------ parameter sets
@pytest.mark.django_db
def test_parameter_set_diff_and_rollback(admin_client):
    p1 = _params(admin_client, base="100.00")
    p2 = _params(admin_client, base="150.00", extra=[{"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "10"}])
    diff = admin_client.get(f"/api/v1/configuration/pricing-parameter-set/{p1['id']}/diff?against={p2['id']}").data
    changes = {c["key"]: c for c in diff["changes"]}
    assert changes["BASE_PREMIUM"]["kind"] == "CHANGED" and changes["BASE_PREMIUM"]["after"]["value"] == "150"
    assert changes["COVERAGE_LOADING_DENTAL"]["kind"] == "ADDED"

    result = admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{p1['id']}/rollback", {"reason": REASON}, format="json")
    assert result.status_code == 200 and result.data["current"]["id"] == p1["id"]
    assert [h["status"] for h in admin_client.get(f"/api/v1/configuration/pricing-parameter-set/{p1['id']}/versions").data] == ["RETIRED", "PUBLISHED"]


@pytest.mark.django_db
def test_parameter_set_rollback_of_a_retired_version_copies_every_parameter(admin_client):
    p1 = _params(admin_client, base="100.00", extra=[{"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "10"}])
    _params(admin_client, base="150.00")
    admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{p1['id']}/retire")
    result = admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{p1['id']}/rollback", {"reason": REASON}, format="json").data
    assert result["current"]["versionNo"] == 3
    diff = admin_client.get(f"/api/v1/configuration/pricing-parameter-set/{p1['id']}/diff?against={result['current']['id']}").data
    assert diff["changes"] == []  # BASE_PREMIUM e COVERAGE_LOADING_DENTAL copiados


# ------------------------------------------------------------------- rules
@pytest.mark.django_db
def test_pricing_rule_diff_and_rollback(admin_client):
    r1 = _rule(admin_client, adjustments=[{"code": "SENIOR", "when": {"ageBand": "70+"}, "amount": "10.00"}])
    r2 = _rule(admin_client, adjustments=[{"code": "SENIOR", "when": {"ageBand": "70+"}, "amount": "25.00"}, {"code": "EXTRA", "when": {}, "amount": "1.00"}])
    diff = admin_client.get(f"/api/v1/configuration/rule-version/{r1['id']}/diff?against={r2['id']}").data
    changes = {c["key"]: c for c in diff["changes"]}
    assert changes["adjustments[0].amount"] == {"kind": "CHANGED", "key": "adjustments[0].amount", "before": "10.00", "after": "25.00"}
    assert changes["adjustments[1].code"]["kind"] == "ADDED"

    admin_client.post(f"/api/v1/configuration/rule-version/{r1['id']}/retire")
    result = admin_client.post(f"/api/v1/configuration/rule-version/{r1['id']}/rollback", {"reason": REASON}, format="json")
    assert result.status_code == 200, result.data
    assert result.data["current"]["versionNo"] == 3 and [r["id"] for r in result.data["retired"]] == [r2["id"]]
    assert admin_client.get(f"/api/v1/configuration/rule-version/{r1['id']}/diff?against={result.data['current']['id']}").data["changes"] == []
