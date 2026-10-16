"""Camada de configuração geral do fornecedor: as contas da plataforma gerem
os parâmetros que valem para todos os tenants (estruturais, impostos legais,
valores por omissão e limites dos operacionais), com versões, aprovação por
outra conta e vigência. O tenant só consulta os obrigatórios e ajusta os
operacionais dentro dos limites."""
from __future__ import annotations

import datetime
import json

import pytest
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework.test import APIClient

from apps.platform_admin.infrastructure.models import PlatformAdmin, PlatformAuditEvent
from tests.quote.test_business_config_e2e import BASE, SCOPE, _values
from tests.quote.conftest import make_client
from tests.quote.test_quotes import _member, _plan, _proposer

PASSWORD = "uma-palavra-passe-longa-1"
REASON = "Atualização legal publicada em Diário da República"
LAW = {"legalReference": "Norma de teste n.º 1/2026, art. 2.º"}
PLATFORM = "/api/v1/platform/system-parameters"


@pytest.fixture(autouse=True)
def _platform_key(settings):
    settings.PLATFORM_ADMIN_JWT_SIGNING_KEY = "platform-tests-signing-secret-32-bytes-min"


def _platform_client(email: str) -> APIClient:
    PlatformAdmin.objects.create(email=email, name=email.split("@")[0], password_hash=make_password(PASSWORD))
    login = APIClient().post("/api/v1/platform/auth/login", {"email": email, "password": PASSWORD}, format="json")
    assert login.status_code == 200, login.content
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['accessToken']}")
    return client


@pytest.fixture
def maker(db):
    return _platform_client("maker@q360.test")


@pytest.fixture
def checker(db):
    return _platform_client("checker@q360.test")


def _publish(maker, checker, code: str, body: dict) -> dict:
    proposed = maker.post(f"{PLATFORM}/{code}/versions", {"reason": REASON, **LAW, **body}, format="json")
    assert proposed.status_code == 201, proposed.data
    approved = checker.post(f"{PLATFORM}/{code}/versions/{proposed.data['versionNo']}/approve", {}, format="json")
    assert approved.status_code == 200, approved.data
    return approved.data


@pytest.mark.django_db
def test_platform_lists_levels_and_tenants_cannot_use_platform_routes(maker, admin_client):
    rows = {r["code"]: r for r in maker.get(PLATFORM).data}
    assert rows["tax.arseg_levy_pct"]["level"] == "PLATFORM_MANDATORY" and rows["tax.arseg_levy_pct"]["value"] == "1"
    assert rows["tax.stamp_duty_pct"]["category"] == "LEGAL" and rows["tax.stamp_duty_pct"]["value"] == "0"
    assert rows["pricing.rounding_policy"]["allowedValues"] == ["OD-006-OFFICIAL-HALF-UP-2DP"]
    assert rows["quote.validity_days"]["level"] == "PLATFORM_DEFAULT"
    assert rows["quote.validity_days"]["tenantOverrides"] == {"count": 0, "outOfLimits": 0}
    assert {r["code"] for r in maker.get(PLATFORM, {"level": "PLATFORM_MANDATORY"}).data} == {
        "pricing.rounding_policy", "pricing.formula", "capital.pro_rata_rule", "tax.stamp_duty_pct", "tax.arseg_levy_pct",
        "legal.age_of_majority", "limits.dependent_max_age_with_proof", "limits.max_acquisition_commission_pct",
        "market.usd_aoa", "market.inflation_pct",
    }
    assert admin_client.get(PLATFORM).status_code in (401, 403)
    assert admin_client.post(f"{PLATFORM}/tax.arseg_levy_pct/versions", {"value": "2", "reason": REASON},
                             format="json").status_code in (401, 403)


@pytest.mark.django_db
def test_legal_tax_needs_a_second_platform_account_and_is_read_only_for_tenants(maker, checker, admin_client):
    proposed = maker.post(f"{PLATFORM}/tax.arseg_levy_pct/versions", {"value": "2", "reason": REASON, **LAW}, format="json")
    assert proposed.status_code == 201 and proposed.data["status"] == "PENDING_APPROVAL"
    # Pendente não vale ainda; uma segunda proposta espera pela decisão da primeira.
    assert admin_client.get("/api/v1/system-parameters/tax.arseg_levy_pct").data["value"] == "1"
    assert maker.post(f"{PLATFORM}/tax.arseg_levy_pct/versions", {"value": "3", "reason": REASON, **LAW},
                      format="json").status_code == 409
    own = maker.post(f"{PLATFORM}/tax.arseg_levy_pct/versions/1/approve", {}, format="json")
    assert own.status_code == 403 and own.data["code"] == "SEC-403"

    approved = checker.post(f"{PLATFORM}/tax.arseg_levy_pct/versions/1/approve", {"note": "Confirmado"}, format="json")
    assert approved.status_code == 200 and approved.data["status"] == "PUBLISHED" and approved.data["effectiveFrom"]
    tenant_view = admin_client.get("/api/v1/system-parameters/tax.arseg_levy_pct").data
    assert tenant_view["value"] == "2" and tenant_view["source"] == "PLATFORM" and tenant_view["platformVersionNo"] == 1
    assert tenant_view["editable"] is False and tenant_view["level"] == "PLATFORM_MANDATORY"
    denied = admin_client.put("/api/v1/system-parameters/tax.arseg_levy_pct",
                              {"value": "0", "rowVersion": 0, "reason": REASON}, format="json")
    assert denied.status_code == 403 and "valor legal" in denied.data["detail"]

    assert set(PlatformAuditEvent.objects.filter(entity_id="tax.arseg_levy_pct").values_list("action", flat=True)) == {
        "platform_parameter.proposed", "platform_parameter.approved",
    }


@pytest.mark.django_db
def test_structural_values_are_limited_to_what_the_engine_executes(maker):
    bad = maker.post(f"{PLATFORM}/pricing.rounding_policy/versions", {"value": "HALF-EVEN", "reason": REASON}, format="json")
    assert bad.status_code == 400 and "nova versão do sistema" in bad.data["detail"]
    assert maker.post(f"{PLATFORM}/capital.pro_rata_rule/versions", {"value": True, "reason": REASON},
                      format="json").status_code == 400
    with_limits = maker.post(f"{PLATFORM}/tax.stamp_duty_pct/versions",
                             {"value": "0", "minimum": "0", "reason": REASON, **LAW}, format="json")
    assert with_limits.status_code == 400
    assert maker.post(f"{PLATFORM}/tax.stamp_duty_pct/versions", {"value": "101", "reason": REASON, **LAW},
                      format="json").status_code == 400
    assert maker.post(f"{PLATFORM}/tax.stamp_duty_pct/versions", {"value": "1", "reason": "curto"},
                      format="json").status_code == 400


@pytest.mark.django_db
def test_future_version_reject_and_rollback(maker, checker, admin_client):
    _publish(maker, checker, "tax.stamp_duty_pct", {"value": "0.5"})
    future = (timezone.now() + datetime.timedelta(days=30)).isoformat()
    _publish(maker, checker, "tax.stamp_duty_pct", {"value": "0.8", "effectiveFrom": future})
    # A versão 2 só vale a partir da vigência: hoje continua a 1.
    assert admin_client.get("/api/v1/system-parameters/tax.stamp_duty_pct").data["value"] == "0.5"
    history = maker.get(f"{PLATFORM}/tax.stamp_duty_pct/versions").data
    assert [(v["versionNo"], v["inEffect"]) for v in history] == [(2, False), (1, True)]

    pending = maker.post(f"{PLATFORM}/tax.stamp_duty_pct/versions", {"value": "9", "reason": REASON, **LAW}, format="json").data
    assert checker.post(f"{PLATFORM}/tax.stamp_duty_pct/versions/{pending['versionNo']}/reject",
                        {"note": "x"}, format="json").status_code == 400
    rejected = checker.post(f"{PLATFORM}/tax.stamp_duty_pct/versions/{pending['versionNo']}/reject",
                            {"note": "Valor sem base legal"}, format="json")
    assert rejected.status_code == 200 and rejected.data["status"] == "REJECTED"
    assert checker.post(f"{PLATFORM}/tax.stamp_duty_pct/versions/{pending['versionNo']}/approve",
                        {}, format="json").status_code == 409

    assert maker.post(f"{PLATFORM}/tax.stamp_duty_pct/rollback", {"versionNo": 3, "reason": REASON},
                      format="json").status_code == 404
    back = maker.post(f"{PLATFORM}/tax.stamp_duty_pct/rollback", {"versionNo": 1, "reason": "Repor o valor anterior"},
                      format="json")
    assert back.status_code == 201 and back.data["action"] == "ROLLBACK_TO_1" and back.data["value"] == "0.5"
    assert back.data["status"] == "PENDING_APPROVAL"


@pytest.mark.django_db
def test_operational_default_and_limits_from_the_platform(maker, checker, admin_client):
    url = "/api/v1/system-parameters/quote.validity_days"
    assert admin_client.put(url, {"value": 90, "rowVersion": 0, "reason": "Prazo comercial alargado"},
                            format="json").status_code == 200
    assert admin_client.get(url).data["source"] == "TENANT"

    # Limites incoerentes ou valor por omissão fora deles são recusados.
    assert maker.post(f"{PLATFORM}/quote.validity_days/versions",
                      {"value": 20, "minimum": 70, "maximum": 60, "reason": REASON}, format="json").status_code == 400
    assert maker.post(f"{PLATFORM}/quote.validity_days/versions",
                      {"value": 80, "maximum": 60, "reason": REASON}, format="json").status_code == 400
    _publish(maker, checker, "quote.validity_days", {"value": 20, "maximum": 60})

    # O valor do tenant (90) ficou fora dos limites: aplica-se o geral até o tenant o ajustar.
    view = admin_client.get(url).data
    assert view["value"] == 20 and view["source"] == "PLATFORM" and view["tenantValueOutOfLimits"] is True
    assert view["constraints"] == {"minimum": 1, "maximum": 60} and view["editable"] is True
    assert maker.get(f"{PLATFORM}/quote.validity_days").data["tenantOverrides"] == {"count": 1, "outOfLimits": 1}
    too_long = admin_client.put(url, {"value": 90, "rowVersion": view["rowVersion"], "reason": "Tentar de novo os 90"},
                                format="json")
    assert too_long.status_code == 400 and "fornecedor" in too_long.data["detail"]
    ok = admin_client.put(url, {"value": 45, "rowVersion": view["rowVersion"], "reason": "Prazo dentro do limite"},
                          format="json")
    assert ok.status_code == 200 and ok.data["value"] == 45 and ok.data["source"] == "TENANT"


@pytest.mark.django_db
def test_legal_tax_rate_comes_from_the_platform_and_reprices_the_quote(maker, checker, admin_client, tenant):
    approver = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")
    plan_ref = _plan(admin_client, product_code="BC-TAX")
    proposer_id = _proposer(admin_client)
    member_id = _member(admin_client, proposer_id=proposer_id)
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {"code": "ELIG-TAX", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    values = _values("100000")
    # O tenant declara a taxa ARSEG com 5 %: a taxa legal (geral) prevalece.
    values["pricing.taxes_fees"] = {"charges": [
        {"code": "ARSEG_LEVY", "description": "Taxa ARSEG", "category": "TAX", "type": "PERCENTAGE", "value": "5",
         "included_in_premium": True},
    ]}
    for key, value in values.items():
        created = admin_client.post(BASE, {"configKey": key, "value": value, "effectiveFrom": "2026-01-01"}, format="json")
        assert created.status_code == 201, created.data
        admin_client.post(f"{BASE}/{created.data['id']}", {"action": "submit"}, format="json")
        assert approver.post(f"{BASE}/{created.data['id']}/approve").status_code == 200

    quote = admin_client.post("/api/v1/quotes", {"proposerId": proposer_id, "planId": plan_ref["planId"]}, format="json").data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    first = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert first.status_code == 200, first.data
    assert first.data["totalAmount"].startswith("101000")  # 100 000 × 1,01 (taxa legal por omissão)
    assert admin_client.post(f"/api/v1/quotes/{quote['id']}/price").data["pricingRunId"] == first.data["pricingRunId"]

    _publish(maker, checker, "tax.arseg_levy_pct", {"value": "2"})
    second = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert second.data["pricingRunId"] != first.data["pricingRunId"]  # a nova taxa geral torna o cálculo desatualizado
    assert second.data["totalAmount"].startswith("102000")
    tax = next(c for c in second.data["components"] if c["code"] == "ARSEG_LEVY")
    assert tax["type"] == "TAX"


@pytest.mark.django_db
def test_legal_values_need_a_source_and_carry_it(maker, checker, admin_client):
    no_source = maker.post(f"{PLATFORM}/tax.arseg_levy_pct/versions", {"value": "2", "reason": REASON}, format="json")
    assert no_source.status_code == 400 and "legalReference" in no_source.data["detail"]
    bad_url = maker.post(f"{PLATFORM}/tax.arseg_levy_pct/versions",
                         {"value": "2", "reason": REASON, **LAW, "sourceUrl": "ftp://x"}, format="json")
    assert bad_url.status_code == 400
    published = _publish(maker, checker, "tax.arseg_levy_pct", {"value": "2", "sourceUrl": "https://arseg.ao/norma"})
    assert published["legalReference"] == LAW["legalReference"] and published["sourceUrl"] == "https://arseg.ao/norma"
    detail = maker.get(f"{PLATFORM}/tax.arseg_levy_pct").data
    assert detail["legalReference"] == LAW["legalReference"] and detail["requiresLegalReference"] is True
    # Um operacional não precisa de fonte.
    assert maker.post(f"{PLATFORM}/quote.validity_days/versions", {"value": 25, "reason": REASON},
                      format="json").status_code == 201
    # Tetos e valores legais: o tenant só consulta.
    denied = admin_client.put("/api/v1/system-parameters/limits.max_acquisition_commission_pct",
                              {"value": "50", "rowVersion": 0, "reason": REASON}, format="json")
    assert denied.status_code == 403 and "teto" in denied.data["detail"]
