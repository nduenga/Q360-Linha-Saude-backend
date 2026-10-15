"""Fórmulas configuráveis de ponta a ponta: criadas pela API (DRAFT),
validadas, rejeitadas com motivo, corrigidas, aprovadas por outro utilizador,
usadas no cálculo real da cotação, explicadas no trace e sem alterar
cálculos anteriores."""
from __future__ import annotations

import json

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import SCOPE, _publish_all
from tests.quote.test_quotes import _member, _plan, _proposer

FORMULAS = "/api/v1/business-config/formulas"

VALUE = {
    "parameters": [{"code": "taxa_gestao", "label": "Taxa de gestão", "value": "0.10", "unit": "RATIO",
                    "min": "0", "max": "1"}],
    "rules": [
        {"code": "gestao", "name": "Encargo de gestão", "target": "VALUE", "expression": "base_total * taxa_gestao"},
        {"code": "com_gestao", "name": "Total com gestão", "purpose": "LOADING", "order": 10,
         "expression": "total_amount + gestao", "variables": ["total_amount", "gestao"]},
        {"code": "minimo", "name": "Prémio mínimo por pessoa", "order": 20, "active": False,
         "expression": "max(total_amount, 999999 * members_count)"},
    ],
}


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


def _priced_quote(client, approver):
    plan_ref = _plan(client, product_code="FORM-E2E")
    proposer_id = _proposer(client)
    member_id = _member(client, proposer_id=proposer_id)
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": "ELIG-FORM", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    _publish_all(client, approver, "100000", "2026-01-01")
    quote = client.post(
        "/api/v1/quotes", {"proposerId": proposer_id, "planId": plan_ref["planId"], "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    priced = client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert priced.status_code == 200, priced.data
    return quote, priced.data


@pytest.mark.django_db
def test_catalog_and_isolated_expression_test(admin_client):
    catalog = admin_client.get(f"{FORMULAS}/catalog").data
    assert {v["name"] for v in catalog["systemVariables"]["QUOTE"]} == {"total_amount", "base_total", "members_count"}
    assert {f["name"] for f in catalog["functions"]} == {"min", "max", "abs", "round"}

    ok = admin_client.post(f"{FORMULAS}/test", {"expression": "round(a * 1.1, 2)", "variables": {"a": "10.005"}},
                           format="json")
    assert ok.status_code == 200 and ok.data == {"valid": True, "result": "11.01", "variables": ["a"]}
    unsafe = admin_client.post(f"{FORMULAS}/test", {"expression": "__import__('os').system('id')"}, format="json")
    assert unsafe.status_code == 400 and unsafe.data["valid"] is False


@pytest.mark.django_db
def test_invalid_formulas_are_rejected_before_saving(admin_client):
    cyclic = {"rules": [{"code": "a", "target": "VALUE", "expression": "b"},
                        {"code": "b", "target": "VALUE", "expression": "a"}]}
    assert admin_client.post(f"{FORMULAS}/validate", {"value": cyclic}, format="json").data["valid"] is False
    created = admin_client.post(FORMULAS, {"value": cyclic, "effectiveFrom": "2026-01-01"}, format="json")
    assert created.status_code == 400 and "circular" in created.data["detail"]

    # o endpoint genérico de configurações aplica a mesma validação
    generic = admin_client.post("/api/v1/business-config/configurations",
                                {"configKey": "pricing.formulas", "value": {"rules": [{"code": "x", "expression": "os.system"}]},
                                 "effectiveFrom": "2026-01-01"}, format="json")
    assert generic.status_code == 400


@pytest.mark.django_db
def test_formula_lifecycle_pricing_traceability_and_history(admin_client, approver):
    quote, before = _priced_quote(admin_client, approver)
    assert before["totalAmount"] == "100000.00"

    # 1. rascunho com análise de dependências
    draft = admin_client.post(FORMULAS, {"value": VALUE, "effectiveFrom": "2026-01-01"}, format="json")
    assert draft.status_code == 201, draft.data
    fid = draft.data["id"]
    assert draft.data["status"] == "DRAFT"
    assert draft.data["analysis"]["evaluationOrder"] == ["com_gestao"]
    assert draft.data["analysis"]["inactive"] == ["minimo"]

    # 2. simulação sem gravar nada
    sim = admin_client.post(f"{FORMULAS}/{fid}/simulate", {"totalAmount": "100000.00", "membersCount": 1}, format="json")
    assert sim.status_code == 200, sim.data
    assert sim.data["total"] == "110000.00"
    assert sim.data["steps"][0]["auxiliaryValues"] == {"gestao": "10000.0000"}
    assert sim.data["skipped"] == [{"code": "minimo", "reason": "INACTIVE"}]

    # 3. um rascunho não afeta o cálculo
    assert admin_client.post(f"/api/v1/quotes/{quote['id']}/price").data["pricingRunId"] == before["pricingRunId"]

    # 4. submeter, rejeitar com motivo (outro utilizador), corrigir, voltar a submeter
    assert admin_client.post(f"{FORMULAS}/{fid}/submit").data["status"] == "PENDING_APPROVAL"
    assert approver.post(f"{FORMULAS}/{fid}/reject", {"reason": "x"}, format="json").status_code == 400
    rejected = approver.post(f"{FORMULAS}/{fid}/reject", {"reason": "Taxa de gestão por confirmar"}, format="json")
    assert rejected.status_code == 200, rejected.data
    assert rejected.data["status"] == "REJECTED"  # R2: estado próprio
    assert rejected.data["metadata"]["lastRejection"]["reason"] == "Taxa de gestão por confirmar"
    assert rejected.data["metadata"]["lastRejection"]["rejectedBy"] == "approver-1"

    corrected = {**VALUE, "parameters": [{**VALUE["parameters"][0], "value": "0.05"}]}
    updated = admin_client.put(f"{FORMULAS}/{fid}", {"value": corrected, "rowVersion": rejected.data["rowVersion"]},
                               format="json")
    assert updated.status_code == 200, updated.data
    assert updated.data["status"] == "DRAFT"  # corrigida, volta a rascunho
    admin_client.post(f"{FORMULAS}/{fid}/submit")

    # 5. o autor não aprova a própria versão; outro utilizador publica
    assert admin_client.post(f"{FORMULAS}/{fid}/approve").status_code == 403
    published = approver.post(f"{FORMULAS}/{fid}/approve")
    assert published.status_code == 200 and published.data["status"] == "PUBLISHED"
    checksum = published.data["checksum"]

    # 6. a versão publicada entra no cálculo real
    after = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert after.status_code == 200, after.data
    assert after.data["pricingRunId"] != before["pricingRunId"]
    assert after.data["totalAmount"] == "105000.00"  # 100000 + 100000 × 0,05
    used = after.data["versions"]["businessConfigurationVersions"]["pricing.formulas"]
    assert used["configurationId"] == fid and used["checksum"] == checksum
    component = next(c for c in after.data["components"] if c["code"] == "com_gestao")
    assert component["sourceCode"] == "BUSINESS_CONFIG:pricing.formulas:com_gestao"

    # sem alterações, o cálculo é reutilizado (reprodutível)
    assert admin_client.post(f"/api/v1/quotes/{quote['id']}/price").data["pricingRunId"] == after.data["pricingRunId"]

    # 7. o trace explica a origem do prémio, incluindo a fórmula ignorada
    steps = admin_client.get(f"/api/v1/pricing/{after.data['pricingRunId']}/explanation").data["steps"]
    applied = next(s for s in steps if s["stepCode"] == "FORMULA_APPLIED")
    assert applied["ruleCode"] == "com_gestao"
    assert applied["input"]["variables"] == {"gestao": "5000.0000", "total_amount": "100000.00"}
    assert any(s["stepCode"] == "FORMULA_SKIPPED" and s["ruleCode"] == "minimo" for s in steps)

    # 8. o cálculo antigo não foi alterado
    old = admin_client.get(f"/api/v1/pricing/{before['pricingRunId']}/explanation").data
    assert not any(s["stepCode"].startswith("FORMULA_") for s in old["steps"])

    # 9. histórico completo da versão
    history = admin_client.get(f"{FORMULAS}/{fid}/history").data["items"]
    assert [h["action"] for h in history] == [
        "BUSINESS_CONFIGURATION_CREATED",
        "BUSINESS_CONFIGURATION_SUBMITTED",
        "BUSINESS_CONFIGURATION_REJECTED",
        "BUSINESS_CONFIGURATION_UPDATED",
        "BUSINESS_CONFIGURATION_SUBMITTED",
        "BUSINESS_CONFIGURATION_PUBLISHED",
    ]
    assert history[2]["reason"] == "Taxa de gestão por confirmar"


@pytest.mark.django_db
def test_versions_can_be_compared(admin_client):
    first = admin_client.post(FORMULAS, {"value": VALUE, "effectiveFrom": "2026-01-01"}, format="json").data
    changed = {**VALUE, "parameters": [{**VALUE["parameters"][0], "value": "0.12"}]}
    second = admin_client.post(FORMULAS, {"value": changed, "effectiveFrom": "2026-02-01"}, format="json").data
    assert second["version"] == first["version"] + 1

    diff = admin_client.get(f"/api/v1/business-config/configurations/{first['id']}/compare", {"with": second["id"]})
    assert diff.status_code == 200, diff.data
    assert diff.data["changes"] == [
        {"path": "parameters[0].value", "change": "CHANGED", "before": "0.10", "after": "0.12"}
    ]
    assert admin_client.get(f"/api/v1/business-config/configurations/{first['id']}/compare").status_code == 400
