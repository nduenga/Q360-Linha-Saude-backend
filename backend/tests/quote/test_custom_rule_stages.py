"""Regras "Quando… então…" (`rules.custom`) além do preço e da aceitação:
elegibilidade (por pessoa), validação (bloqueia o envio) e fluxo (exige um
perfil para aprovar). Tudo configurado pelo tenant, sem código."""
from __future__ import annotations

import json

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import SCOPE, _publish, _publish_all
from tests.quote.test_quotes import _member, _plan, _proposer

RULE = {"active": True, "order": 1}


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


def _quote(admin_client, approver, product_code: str) -> dict:
    plan_ref = _plan(admin_client, product_code=product_code)
    proposer_id = _proposer(admin_client)
    member_id = _member(admin_client, proposer_id=proposer_id)
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {"code": f"ELIG-{product_code}", "name": "Eligibility", "ruleDomain": "ELIGIBILITY",
         "effectiveFrom": "2026-01-01", "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    _publish_all(admin_client, approver, "100000", "2026-01-01")
    quote = admin_client.post("/api/v1/quotes", {"proposerId": proposer_id, "planId": plan_ref["planId"]}, format="json").data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    return {"quote": quote, "memberId": member_id, "proposerId": proposer_id, **plan_ref}


@pytest.mark.django_db
def test_validation_blocks_submission_and_workflow_requires_a_role(admin_client, approver, tenant):
    scope = _quote(admin_client, approver, "RULE-STAGES")
    quote_id = scope["quote"]["id"]
    validation = {**RULE, "name": "Grupo mínimo", "code": "MIN_PEOPLE", "scope": "QUOTE", "field": "members_count",
                  "operator": "LT", "value": "2", "action": "VALIDATION_ERROR",
                  "message": "A cotação tem de ter pelo menos 2 pessoas"}
    workflow = {**RULE, "name": "Prémio elevado", "code": "BIG_PREMIUM", "scope": "QUOTE", "field": "total_premium",
                "operator": "GTE", "value": "50000", "action": "REQUIRE_APPROVAL_BY_ROLE", "role": "SUBSCRIPTION_MANAGER",
                "stage": "WORKFLOW", "order": 2}
    _publish(admin_client, approver, "rules.custom", {"rules": [validation, workflow]})

    assert admin_client.post(f"/api/v1/quotes/{quote_id}/price").status_code == 200
    requirements = admin_client.get(f"/api/v1/quotes/{quote_id}/requirements").data
    error = next(e for e in requirements["errors"] if e["code"] == "CUSTOM_RULE_VALIDATION_ERROR")
    assert error["stage"] == "VALIDATION" and error["message"] == "A cotação tem de ter pelo menos 2 pessoas"
    role_item = next(i for i in requirements["info"] if i["code"] == "CUSTOM_RULE_APPROVAL_ROLE")
    assert role_item["requiredRole"] == "SUBSCRIPTION_MANAGER" and role_item["stage"] == "WORKFLOW"
    ready = admin_client.get(f"/api/v1/quotes/{quote_id}").data
    blocked = admin_client.post(f"/api/v1/quotes/{quote_id}/submit", {"rowVersion": ready["rowVersion"]}, format="json")
    assert blocked.status_code >= 400 and "pelo menos 2 pessoas" in blocked.data["detail"]

    # Desativar a validação (nova versão): o envio passa; a aprovação exige o perfil.
    _publish(admin_client, approver, "rules.custom", {"rules": [{**validation, "active": False}, workflow]})
    admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    ready = admin_client.get(f"/api/v1/quotes/{quote_id}").data
    submitted = admin_client.post(f"/api/v1/quotes/{quote_id}/submit", {"rowVersion": ready["rowVersion"]}, format="json")
    assert submitted.status_code == 200, submitted.data

    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write q360.approve",
                             actor_id="subscriber-1")
    decision = {"decision": "APPROVE", "reasonCode": "MEETS_CRITERIA", "rowVersion": submitted.data["rowVersion"]}
    denied = subscriber.post(f"/api/v1/quotes/{quote_id}/decision", decision, format="json")
    assert denied.status_code == 403 and "SUBSCRIPTION_MANAGER" in denied.data["detail"]
    manager = make_client(tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope="q360.read q360.write q360.approve",
                          actor_id="manager-1")
    approved = manager.post(f"/api/v1/quotes/{quote_id}/decision", decision, format="json")
    assert approved.status_code == 200 and approved.data["status"] == "APPROVED"


@pytest.mark.django_db
def test_eligibility_rules_stop_or_refer_a_person(admin_client, approver):
    scope = _quote(admin_client, approver, "RULE-ELIG")
    body = {"proposerId": scope["proposerId"], "memberId": scope["memberId"], "planId": scope["planId"],
            "effectiveDate": "2026-06-01", "context": {}}
    assert admin_client.post("/api/v1/eligibility/evaluate", body, format="json").data["decision"] == "ELIGIBLE"

    refer = {**RULE, "name": "Acima dos 30", "code": "OVER_30", "scope": "PERSON", "field": "age", "operator": "GTE",
             "value": "30", "action": "REFER_TO_UNDERWRITING", "message": "Analisar historial"}
    _publish(admin_client, approver, "rules.custom", {"rules": [refer]})
    referred = admin_client.post("/api/v1/eligibility/evaluate", body, format="json").data
    assert referred["decision"] == "REFERRAL"
    assert {"code": "ELIG-CUSTOM-RULE", "severity": "WARNING", "message": "Analisar historial"} in [
        {k: m[k] for k in ("code", "severity", "message")} for m in referred["messages"]
    ]

    stop = {**RULE, "name": "Plano só até aos 35", "code": "MAX_35", "scope": "PERSON", "field": "age", "operator": "GT",
            "value": "35", "action": "NOT_ELIGIBLE", "message": "Idade acima do limite do plano", "order": 2}
    _publish(admin_client, approver, "rules.custom", {"rules": [refer, stop]})
    stopped = admin_client.post("/api/v1/eligibility/evaluate", body, format="json").data
    assert stopped["decision"] == "HARD_STOP"
    assert [m["message"] for m in stopped["messages"] if m["code"] == "ELIG-CUSTOM-RULE"] == ["Idade acima do limite do plano"]
    # Na cotação, a mesma regra aparece como erro que bloqueia o envio.
    requirements = admin_client.get(f"/api/v1/quotes/{scope['quote']['id']}/requirements").data
    assert any(e["code"] == "CUSTOM_RULE_NOT_ELIGIBLE" and e["stage"] == "ELIGIBILITY" for e in requirements["errors"])
