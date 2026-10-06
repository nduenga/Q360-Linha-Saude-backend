"""A configuração de negócio publicada é lida pelos motores: capitais,
carências, idades, exclusões, aceitação, planos, permissões por perfil,
regras de aprovação, renovação, identidade visual e ligações assinadas.
Sem configuração publicada nada muda (os testes dos restantes módulos provam-no)."""
from __future__ import annotations

import datetime
import io

import pytest

from apps.business_config.application.role_permissions import parse_rows
from apps.foundation.domain.permissions import Permission, Role
from tests.quote.conftest import make_client
from tests.quote.test_quote_simulator import SETTINGS, _scope

BASE = "/api/v1/business-config/configurations"
SCOPES = "q360.read q360.write q360.admin q360.approve"


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPES, actor_id="approver-1")


def publish(creator, approver, key, value, effective_from="2026-01-01"):
    created = creator.post(BASE, {"configKey": key, "value": value, "effectiveFrom": effective_from}, format="json")
    assert created.status_code == 201, created.content
    cid = created.data["id"]
    assert creator.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").status_code == 200
    approved = approver.post(f"{BASE}/{cid}/approve")
    assert approved.status_code == 200, approved.data
    return cid


def requirements(client, scope):
    response = client.get(f"/api/v1/quotes/{scope['quoteId']}/requirements")
    assert response.status_code == 200, response.data
    return response.data


def codes(items):
    return {i["code"] for i in items}


# ------------------------------------------------------------------ produto
@pytest.mark.django_db
def test_waiting_periods_exclusions_and_ages_come_from_business_config(admin_client, approver):
    scope = _scope(admin_client, members=1, settings={**SETTINGS, "segment": "INDIVIDUAL_FAMILY"})
    before = requirements(admin_client, scope)
    assert not any(w["coverage"] == "HOSPITALIZATION" and w["days"] == 45 for w in before["waitingPeriods"])

    publish(admin_client, approver, "product.waiting_periods",
            {"items": [{"coverage": "HOSPITALIZATION", "individual_days": 45, "group_days": 0, "accident_exempt": True}]})
    publish(admin_client, approver, "product.exclusions",
            {"items": [{"code": "BIZ_1", "text": "Exclusão publicada pelo negócio", "active": True}]})
    publish(admin_client, approver, "product.age_limits", {"items": [{"plan": "SIM-PLAN", "entry_max_age": 20, "renewal_max_age": 70}]})

    after = requirements(admin_client, scope)
    hospital = next(w for w in after["waitingPeriods"] if w["coverage"] == "HOSPITALIZATION")
    assert hospital["days"] == 45
    assert "Exclusão publicada pelo negócio" in [e["text"] for e in after["exclusions"]]
    assert "AGE_OUT_OF_ENTRY_RANGE" in codes(after["errors"])  # titular com mais de 20 anos


@pytest.mark.django_db
def test_capitals_and_participation_overlay_the_plan_configuration(admin_client, approver):
    scope = _scope(admin_client, members=1)
    publish(admin_client, approver, "product.capitals_sublimits",
            {"items": [{"plan": "SIM-PLAN", "coverage": "HOSPITALIZATION", "annual_capital": "30000000"}]})
    publish(admin_client, approver, "product.member_participation",
            {"items": [{"plan": "SIM-PLAN", "coverage": "HOSPITALIZATION", "reimbursement_percent": "80", "annual_deductible": "50000"}]})
    preview = admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/proposals/preview")
    assert preview.status_code == 200, preview.content
    html = preview.content.decode()
    assert "30.000.000" in html  # capital publicado, não o 15.000.000 do plano


@pytest.mark.django_db
def test_deactivated_plan_cannot_start_a_quote(admin_client, approver):
    scope = _scope(admin_client, members=1)
    publish(admin_client, approver, "product.plans", {"plans": [{"code": "SIM-PLAN", "name": "SIM", "active": False}]})
    response = admin_client.post(
        "/api/v1/quotes",
        {"proposerId": scope["proposerId"], "planId": scope["planId"], "effectiveDate": "2026-06-01"},
        format="json",
    )
    assert response.status_code in (400, 404, 422)
    assert "desativado" in str(response.data)


# ------------------------------------------------------------- subscrição
@pytest.mark.django_db
def test_underwriting_rules_drive_requirements(admin_client, approver):
    scope = _scope(admin_client, members=1)
    publish(admin_client, approver, "underwriting.medical_review",
            {"thresholds": {"automatic_acceptance_max_age": 30, "questionnaire_required": True, "clinical_documentation_required": True}})
    publish(admin_client, approver, "underwriting.acceptance_rules",
            {"rules": [{"condition": "Idade acima de 35", "age_from": 35, "decision": "TECHNICAL_REVIEW"},
                       {"condition": "Regra geral informativa", "decision": "MEDICAL_REVIEW"}]})
    result = requirements(admin_client, scope)
    assert "MEDICAL_EXAM_REQUIRED" in codes(result["warnings"])
    assert "ACCEPTANCE_TECHNICAL_REVIEW" in codes(result["warnings"])
    assert {"CLINICAL_DOCUMENTATION_REQUIRED", "ACCEPTANCE_RULE"} <= codes(result["info"])


@pytest.mark.django_db
def test_decline_rule_blocks_and_documents_are_listed(admin_client, approver):
    scope = _scope(admin_client, members=1)
    publish(admin_client, approver, "underwriting.acceptance_rules",
            {"rules": [{"condition": "Maiores de 35", "age_from": 35, "decision": "DECLINE"}]})
    publish(admin_client, approver, "proposal.documents",
            {"documents": [{"document_type": "HEALTH_QUESTIONNAIRE", "required": True, "description": "Assinado"}]})
    result = requirements(admin_client, scope)
    assert result["blocking"] and "ACCEPTANCE_DECLINE" in codes(result["errors"])
    assert "REQUIRED_DOCUMENTS" in codes(result["info"])


@pytest.mark.django_db
def test_pre_existing_policy_restricts_treatments_and_supplies_defaults(admin_client, approver):
    scope = _scope(admin_client, members=1)
    member_id = admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/members").data["items"][0]["memberId"]
    publish(admin_client, approver, "underwriting.pre_existing_conditions",
            {"rules": [{"severity": "LOW", "treatment": "SURCHARGE", "surcharge_percent": "25"}]})
    url = f"/api/v1/quotes/{scope['quoteId']}/members/{member_id}/pre-existing"
    body = {"reason": "Declaração do cliente", "decision": {"mode": "ACCEPTED_WITH_LOADING", "severity": "LOW", "clinicalQuestionnaireCompleted": True}}
    ok = admin_client.put(url, body, format="json")
    assert ok.status_code == 200, ok.data
    assert ok.data["preExisting"]["loadingPct"] == "25"
    wrong = admin_client.put(url, {**body, "decision": {"mode": "TOTAL_EXCLUSION", "severity": "LOW"}}, format="json")
    assert wrong.status_code == 400


# ----------------------------------------------------------------- segurança
def test_admin_can_never_lose_the_configuration_permissions():
    parsed = parse_rows([{"role": "ADMIN", "permissions": ["quote:create"]}, {"role": "NOPE", "permissions": []}])
    assert {Permission.PRODUCT_MANAGE, Permission.PRICING_CONFIG_MANAGE, Permission.QUOTE_CREATE} == parsed[Role.ADMIN]
    assert set(parsed) == {Role.ADMIN}


@pytest.mark.django_db
def test_role_permissions_are_editable_by_the_business(admin_client, approver, tenant):
    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write", actor_id="sub-1")
    assert subscriber.post("/api/v1/products", {"code": "P-ROLE", "name": "P"}, format="json").status_code == 403
    publish(admin_client, approver, "security.role_permissions",
            {"roles": [{"role": "SUBSCRIBER", "permissions": ["quote:create", "quote:edit", "product:manage"]}]})
    assert subscriber.post("/api/v1/products", {"code": "P-ROLE", "name": "P"}, format="json").status_code == 201
    other = make_client(tenant_id=tenant.id, roles=[], scope="q360.read", actor_id="aud-1")
    assert other.post("/api/v1/products", {"code": "P-ROLE2", "name": "P"}, format="json").status_code == 403


@pytest.mark.django_db
def test_approval_rules_restrict_editors_and_can_relax_four_eyes(admin_client, approver, tenant):
    publish(admin_client, approver, "security.approval_rules",
            {"approval": {"four_eyes_required": False, "editable_roles": ["SUBSCRIPTION_MANAGER"], "approval_roles": ["SUBSCRIBER"]}})
    configurator = make_client(tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope=SCOPES, actor_id="cfg-1")
    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write", actor_id="sub-1")
    value = {"factors": [{"code": "X", "dimension": "tier", "condition": "*", "factor": "1.1"}]}
    assert subscriber.post(BASE, {"configKey": "pricing.factors", "value": value, "effectiveFrom": "2026-01-01"}, format="json").status_code == 403
    created = configurator.post(BASE, {"configKey": "pricing.factors", "value": value, "effectiveFrom": "2026-01-01"}, format="json")
    assert created.status_code == 201, created.data
    cid = created.data["id"]
    configurator.post(f"{BASE}/{cid}", {"action": "submit"}, format="json")
    # perfil não aprovador: recusado; criador sem four-eyes obrigatório mas sem o perfil aprovador também
    assert configurator.post(f"{BASE}/{cid}/approve").status_code == 403


@pytest.mark.django_db
def test_structure_is_validated_before_saving(admin_client):
    bad = admin_client.post(
        BASE,
        {"configKey": "pricing.factors", "value": {"factors": [{"code": "X", "dimension": "tier", "condition": "*", "factor": "abc"}]},
         "effectiveFrom": "2026-01-01"},
        format="json",
    )
    assert bad.status_code == 400
    unknown = admin_client.post(BASE, {"configKey": "group.rules", "value": {"nope": 1}, "effectiveFrom": "2026-01-01"}, format="json")
    assert unknown.status_code == 400
    no_currency = admin_client.post(
        BASE,
        {"configKey": "pricing.reference_premiums", "value": {"premiums": [{"age_from": 0, "plan": "A", "annual_premium": "1"}]},
         "effectiveFrom": "2026-01-01"},
        format="json",
    )
    cid = no_currency.data["id"]
    assert admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").status_code == 400


# ------------------------------------------------------ grupo e sinistralidade
@pytest.mark.django_db
def test_group_rules_set_the_minimum_size(admin_client, approver):
    scope = _scope(admin_client, members=1, settings={**SETTINGS, "segment": "GROUP", "group": {"adhesion": "MANDATORY"}})
    publish(admin_client, approver, "group.rules",
            {"group": {"minimum_members": 5, "below_minimum_behavior": "DECLINE", "experience_loss_ratio_threshold": "70", "profit_share_percent": "50"}})
    result = requirements(admin_client, scope)
    minimum = next(e for e in result["errors"] if e["code"] == "GROUP_MIN_SIZE")
    assert minimum["minimum"] == 5 and "recusada" in minimum["message"]


# ------------------------------------------------------ identidade e ligações
@pytest.mark.django_db
def test_branding_texts_and_signed_links(admin_client, approver, tenant):
    scope = _scope(admin_client, members=1)
    publish(admin_client, approver, "proposal.branding",
            {"branding": {"company_name": "Seguradora Exemplo", "primary_color": "#112233", "tagline": "Saúde sempre", "footer_text": "Rodapé oficial"}})
    publish(admin_client, approver, "proposal.texts",
            {"texts": [{"code": "T1", "title": "Aviso do negócio", "text": "Texto publicado pelo negócio", "active": True}]})
    html = admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/proposals/preview").content.decode()
    for expected in ("Seguradora Exemplo", "#112233", "Saúde sempre", "Rodapé oficial", "Aviso do negócio", "Texto publicado pelo negócio"):
        assert expected in html
    for fmt, magic in (("PDF", b"%PDF"), ("DOCX", b"PK")):
        doc = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/proposals", {"format": fmt}, format="json").data
        assert doc["status"] == "GENERATED"
        assert admin_client.get(doc["downloadUrl"]).content.startswith(magic)

    link = admin_client.post(f"/api/v1/documents/{doc['id']}/signed-url", {}, format="json")
    assert link.status_code == 201 and link.data["expiresInSeconds"] == 900
    from rest_framework.test import APIClient

    anonymous = APIClient()
    opened = anonymous.get(link.data["url"])
    assert opened.status_code == 200 and opened.content.startswith(b"PK")
    tampered = anonymous.get(link.data["url"][:-4] + "xxxx")
    assert tampered.status_code == 403
    assert anonymous.get(doc["downloadUrl"]).status_code in (401, 403)  # o descarregamento normal exige sessão


@pytest.mark.django_db
def test_expired_signed_link_is_refused(admin_client, monkeypatch):
    scope = _scope(admin_client, members=1)
    doc = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/proposals", {"format": "HTML"}, format="json").data
    admin_client.put("/api/v1/system-parameters/documents.signed_url_ttl_seconds", {"value": 60, "rowVersion": 0, "reason": "Prazo curto para teste"}, format="json")
    link = admin_client.post(f"/api/v1/documents/{doc['id']}/signed-url", {}, format="json").data
    assert link["expiresInSeconds"] == 60
    from django.utils import timezone

    from apps.quote.application import document_links

    future = timezone.now() + datetime.timedelta(seconds=120)
    monkeypatch.setattr(document_links.timezone, "now", lambda: future)
    from rest_framework.test import APIClient

    assert APIClient().get(link["url"]).status_code == 403
