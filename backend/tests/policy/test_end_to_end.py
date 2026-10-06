"""Teste de integridade de ponta a ponta de tudo o que foi construído para o
simulador GTE, incluindo o portal do cliente.

Percorre, por esta ordem, com a API real e uma única base de dados:
modelos de mercado do PDF -> configuração de tarifas -> cotação com opção A–E,
cobertura opcional, ajuste e preexistência -> requisitos -> versões ->
cenários e comparação -> proposta PDF -> aprovação -> apólice e pagamento ->
verificação de cobertura (opcionais não contratadas, carências) -> portal do
cliente (OTP, apólices, coberturas contratadas, elegibilidade) -> renovação e
indexação -> sinistralidade e projeção ligada a cenário -> simulação de
impacto e rollback de tarifas -> parâmetros globais -> auditoria -> isolamento
entre tenants.
"""
from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from tests.policy.conftest import make_client
from tests.policy.test_issuance import _SIGN_BODY, _approver

EMAIL = "cliente.e2e@example.com"
REGISTRATION = "555666777LA042"


def _publish(client, kind, config_id):
    resp = client.post(f"/api/v1/configuration/{kind}/{config_id}/publish")
    assert resp.status_code == 200, resp.data
    return resp.data


def _configure_pricing(client, *, base="1000.00"):
    params = client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "E2E-PARAMS", "effectiveFrom": "2026-01-01",
         "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": base},
                        {"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "8"},
                        {"code": "COVERAGE_LOADING_MEDICAL_EVACUATION", "valueType": "DECIMAL", "value": "20"}]},
        format="json",
    ).data
    _publish(client, "pricing-parameter-set", params["id"])
    table = client.post(
        "/api/v1/rating-tables",
        {"code": "E2E-TABLE", "name": "E2E", "effectiveFrom": "2026-01-01", "currencyCode": "AOA",
         "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00", "priority": -1},
                     {"factorCode": "TIER_FACTOR", "dimensions": {"tier": "MEDIUM"}, "factorValue": "1.20"},
                     {"factorCode": "HOSPITAL_CAPITAL", "dimensions": {"capital.HOSPITALIZATION": "15000000"}, "factorValue": "1.10"}]},
        format="json",
    ).data
    _publish(client, "rating-table", table["id"])
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": "E2E-ELIG", "name": "e2e", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    _publish(client, "rule-version", rule["id"])


def _total(client, quote_id) -> Decimal:
    quote = client.get(f"/api/v1/quotes/{quote_id}").data
    return Decimal(client.get(f"/api/v1/pricing/runs/{quote['latestPricingRunId']}").data["totalAmount"])


def _portal_login(tenant, policy_number):
    anonymous = APIClient()
    anonymous.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/request-access",
        {"policyNumber": policy_number, "registrationNumber": REGISTRATION, "email": EMAIL}, format="json",
    )
    otp = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()
    verified = anonymous.post(
        f"/api/v1/customer-portal/{tenant.id}/auth/verify-otp",
        {"policyNumber": policy_number, "registrationNumber": REGISTRATION, "email": EMAIL, "otp": otp}, format="json",
    )
    assert verified.status_code == 200, verified.data
    portal = APIClient()
    portal.credentials(HTTP_AUTHORIZATION=f"Bearer {verified.data['accessToken']}")
    return portal


@pytest.mark.django_db
def test_full_lifecycle_from_market_templates_to_portal_and_renewal(admin_client, tenant, settings):
    approver = _approver(tenant)
    auditor = make_client(tenant_id=tenant.id, roles=[], scope="q360.read q360.audit", actor_id="auditor-1")

    # ------------------------------------------------ 1. modelos do PDF + tarifas
    market = admin_client.post("/api/v1/product-templates/market", {}, format="json")
    assert market.status_code == 200 and all(p["valid"] for p in market.data["plans"])
    plans = {p["code"]: p for p in admin_client.get("/api/v1/plans?size=50").data["items"]}
    medio = plans["IND-MEDIO"]
    _configure_pricing(admin_client)

    # ----------------------------------------------------------- 2. cliente + cotação
    proposer = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "Cliente E2E", "registrationNumber": REGISTRATION,
         "email": EMAIL, "phone": "+244900000099"},
    ).data
    holder = admin_client.post("/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1985-03-10", "firstName": "Titular"}).data
    spouse = admin_client.post("/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "CONJUGE", "dateOfBirth": "1988-07-21", "firstName": "Conjuge"}).data
    quote = admin_client.post(
        "/api/v1/quotes", {"proposerId": proposer["id"], "planId": medio["id"], "effectiveDate": "2026-06-01"}, format="json"
    ).data
    for member in (holder, spouse):
        assert admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json").status_code == 200
    assert admin_client.post(f"/api/v1/quotes/{quote['id']}/price").status_code == 200
    # 1000 x 1,10 (capital 15M) x 1,20 (escalão Médio) = 1.320 por pessoa; opção B = 0 %
    assert _total(admin_client, quote["id"]) == Decimal("2640.00")

    # --------------------------- 3. opção A–E, opcional escolhida, ajuste, preexistência
    current = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    selected = admin_client.put(
        f"/api/v1/quotes/{quote['id']}/selection",
        {"selection": {"participationOption": "C", "optionalBenefitCodes": ["DENTAL"]}, "rowVersion": current["rowVersion"]}, format="json",
    )
    assert selected.status_code == 200, selected.data
    # 1.320 x 0,93 (opção C) + 80 (8 % do prémio base, estomatologia) = 1.307,60 por pessoa
    assert _total(admin_client, quote["id"]) == Decimal("2615.20")

    dry = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/adjustments?dryRun=true", {"kind": "SURCHARGE_PERCENT", "value": "5"}, format="json"
    )
    assert dry.data["newTotal"] == "2745.96" and dry.data["requiresApproval"] is False
    applied = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/adjustments",
        {"kind": "SURCHARGE_PERCENT", "value": "5", "reason": "Agravamento por sinistralidade do agregado"}, format="json",
    )
    assert applied.status_code == 201 and applied.data["quote"]["status"] == "READY"
    assert _total(admin_client, quote["id"]) == Decimal("2745.96")

    decision = admin_client.put(
        f"/api/v1/quotes/{quote['id']}/members/{spouse['id']}/pre-existing",
        {"decision": {"mode": "TOTAL_EXCLUSION"}, "reason": "Exclusão total da doença declarada"}, format="json",
    )
    assert decision.status_code == 200

    # -------------------------------------------------------- 4. requisitos e versões
    requirements = admin_client.get(f"/api/v1/quotes/{quote['id']}/requirements").data
    assert requirements["blocking"] is False
    assert {"CLINICAL_QUESTIONNAIRE_REQUIRED", "NETWORK_COVERAGE"} <= {w["code"] for w in requirements["warnings"]}
    versions = admin_client.get(f"/api/v1/quotes/{quote['id']}/versions").data
    assert len(versions) >= 3 and versions[0]["totalAmount"] == "2745.96"

    # --------------------------------------------- 5. cenários, comparação e proposta
    base = admin_client.post(f"/api/v1/quotes/{quote['id']}/scenarios", {"name": "Proposta escolhida"}, format="json").data
    rich = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/scenarios",
        {"name": "Com evacuação", "parameters": {"selection": {"participationOption": "C", "optionalBenefitCodes": ["DENTAL", "MEDICAL_EVACUATION"]}}},
        format="json",
    ).data
    assert Decimal(rich["result"]["totalAmount"]) > Decimal(base["result"]["totalAmount"]) - Decimal("1")
    compare = admin_client.get(f"/api/v1/quotes/{quote['id']}/scenarios/compare").data
    assert any(c["code"] == "MEDICAL_EVACUATION" and c["differs"] for c in compare["coverages"])
    admin_client.post(f"/api/v1/scenarios/{base['id']}/select", {}, format="json")
    proposal = admin_client.post(f"/api/v1/quotes/{quote['id']}/proposals", {"format": "PDF"}, format="json")
    assert proposal.status_code == 201 and proposal.data["scenarioId"] == base["id"]
    assert admin_client.get(proposal.data["downloadUrl"]).content.startswith(b"%PDF")
    html = admin_client.get(f"/api/v1/quotes/{quote['id']}/proposals/preview").content.decode()
    assert "Estomatologia e ortodontia (opcional escolhida)" in html and "Exclusão total" in html

    # ------------------------------------------------ 6. aprovação, apólice e pagamento
    ready = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    submitted = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": ready["rowVersion"]}, format="json")
    assert submitted.status_code == 200, submitted.data
    approved = approver.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted.data["rowVersion"]}, format="json",
    )
    assert approved.status_code == 200, approved.data
    policy = approver.post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": approved.data["rowVersion"]}, format="json",
    ).data
    active = approver.post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": "2026-06-10T16:00:00Z", "rowVersion": policy["rowVersion"]}, format="json",
    ).data
    assert active["status"] == "ACTIVE" and active["startDate"] == "2026-06-11"
    start = datetime.date.fromisoformat(active["startDate"])

    # ------------------------------ 7. cobertura: opcional contratada vs apenas oferecida
    def coverage(category, days_after, member=holder, event=None):
        date = (start + datetime.timedelta(days=days_after)).isoformat()
        extra = f"&eventType={event}" if event else ""
        return admin_client.get(
            f"/api/v1/policies/{policy['id']}/coverage?memberId={member['id']}&benefitCategory={category}&date={date}{extra}"
        ).data

    assert coverage("DENTAL", 10)["reasonCode"] == "IN_WAITING_PERIOD"  # carência de 90 dias da configuração
    assert coverage("DENTAL", 100)["covered"] is True
    assert coverage("MEDICAL_EVACUATION", 150)["reasonCode"] == "BENEFIT_NOT_IN_PLAN"  # oferecida, não contratada
    assert coverage("HOSPITALIZATION", 100)["covered"] is True
    # PDF: urgência 30 dias por doença, sem carência em acidente
    assert coverage("EMERGENCY", 5)["reasonCode"] == "IN_WAITING_PERIOD"
    assert coverage("EMERGENCY", 5, event="ACCIDENT")["covered"] is True
    assert coverage("DENTAL", 10, event="ACCIDENT")["covered"] is True  # estomatologia: acidente dispensa a carência

    # ------------------------------------------------------------ 8. portal do cliente
    portal = _portal_login(tenant, active["policyNumber"])
    mine = portal.get("/api/v1/customer-portal/me").data["policies"]
    assert [item["policy"]["policyNumber"] for item in mine] == [active["policyNumber"]]
    benefits = portal.get(f"/api/v1/customer-portal/plan-benefits?policyNumber={active['policyNumber']}").data
    codes = {b["benefit"]["code"] for b in benefits["benefits"]}
    assert {"HOSPITALIZATION", "AMBULATORY_SURGERY", "EMERGENCY", "DENTAL", "OUTPATIENT"} <= codes
    assert "MEDICAL_EVACUATION" not in codes and "PHARMACY" not in codes
    hospital = next(b for b in benefits["benefits"] if b["benefit"]["code"] == "HOSPITALIZATION")
    assert hospital["configurationJson"]["limits"][0] == {"kind": "ANNUAL_PER_PERSON", "amount": "15000000"}
    portal_cov = portal.get(
        f"/api/v1/customer-portal/coverage?policyNumber={active['policyNumber']}&benefitCategory=MEDICAL_EVACUATION"
        f"&date={(start + datetime.timedelta(days=150)).isoformat()}"
    ).data
    assert all(r["reasonCode"] == "BENEFIT_NOT_IN_PLAN" for r in portal_cov["results"])
    eligibility = portal.post("/api/v1/customer-portal/eligibility", {"policyNumber": active["policyNumber"]}, format="json")
    assert eligibility.status_code == 200 and len(eligibility.data["results"]) == 2
    assert APIClient().get("/api/v1/customer-portal/me").status_code == 401

    # ------------------------------------------------------- 9. renovação e indexação
    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json")
    assert renewal.status_code == 201, renewal.data
    renewed = renewal.data
    assert renewed["quoteType"] == "RENEWAL" and renewed["effectiveDate"] == "2027-06-11"
    assert renewed["renewal"]["previousPremium"]["amount"] == "2745.96"
    assert renewed["selection"]["optionalBenefitCodes"] == ["DENTAL"] and renewed["selection"]["participationOption"] == "C"
    assert len(renewed["renewal"]["carriedMembers"]) == 2 and renewed["renewal"]["skippedMembers"] == []
    plan_settings = admin_client.get(f"/api/v1/plans/{medio['id']}").data
    admin_client.patch(
        f"/api/v1/plans/{medio['id']}",
        {"name": plan_settings["name"], "rowVersion": plan_settings["rowVersion"],
         "settings": {**plan_settings["settings"], "capitalIndexation": {"medicalInflationPct": "10", "reviewOnRenewal": True}}},
        format="json",
    )
    indexed = admin_client.post(
        f"/api/v1/quotes/{renewed['id']}/renewal/indexation", {"reason": "Revisão anual dos capitais"}, format="json"
    )
    assert indexed.status_code == 200, indexed.data
    assert indexed.data["coverages"]["HOSPITALIZATION"][0]["amount"] == "16500000"

    # ------------------------------------- 10. sinistralidade e projeção ligada a cenário
    claims_csv = "occurrence_date,benefit_code,paid_amount\n" + "\n".join(f"2025-{m:02d}-10,DENTAL,10000" for m in range(1, 13))
    premiums_csv = "period_start,period_end,premium_amount,insured_count\n2025-01-01,2025-12-31,200000,2\n"
    for kind, content in (("CLAIMS", claims_csv), ("PREMIUMS", premiums_csv)):
        resp = admin_client.post(
            "/api/v1/claims/imports",
            {"file": SimpleUploadedFile("d.csv", content.encode()), "kind": kind, "proposerId": proposer["id"]}, format="multipart",
        )
        assert resp.status_code == 201, resp.data
    summary = admin_client.get(f"/api/v1/claims/summary?proposerId={proposer['id']}").data
    assert summary["lossRatioPct"] == "60.00" and summary["claims"]["count"] == 12
    projection = admin_client.post(
        "/api/v1/claims/projections",
        {"proposerId": proposer["id"], "assumptions": {
            "horizonMonths": 12, "targetLossRatioPct": "70",
            "scenarios": {"OPTIMISTIC": {"medicalInflationPct": "0", "frequencyTrendPct": "0"},
                          "BASE": {"medicalInflationPct": "10", "frequencyTrendPct": "0"},
                          "PESSIMISTIC": {"medicalInflationPct": "20", "frequencyTrendPct": "5"}}}},
        format="json",
    )
    assert projection.status_code == 201, projection.data
    linked = admin_client.post(
        f"/api/v1/quotes/{renewed['id']}/scenarios",
        {"name": "Renovação pessimista", "parameters": {"projection": {"projectionRunId": projection.data["id"], "scenario": "PESSIMISTIC"}}},
        format="json",
    )
    assert linked.status_code == 201 and linked.data["parameters"]["projection"]["scenario"] == "PESSIMISTIC"
    context = admin_client.get(f"/api/v1/quotes/{renewed['id']}/claims-context").data
    assert context["available"] is True and context["threeYearsAvailable"] is False

    # ------------------------------- 11. impacto e rollback de tarifas, parâmetros globais
    draft = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "E2E-PARAMS", "effectiveFrom": "2026-01-01",
         "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "1200.00"}]}, format="json",
    ).data
    impact = admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{draft['id']}/impact-simulation", {}, format="json")
    assert impact.status_code == 200 and impact.data["compared"] >= 1 and Decimal(impact.data["totals"]["delta"]) > 0
    published = _publish(admin_client, "pricing-parameter-set", draft["id"])
    rolled = admin_client.post(
        f"/api/v1/configuration/pricing-parameter-set/{published['id']}/rollback", {"reason": "Tarifa publicada por engano"}, format="json"
    )
    assert rolled.status_code == 409  # a v2 é a atual: reverte-se para a v1
    first = next(v for v in admin_client.get(f"/api/v1/configuration/pricing-parameter-set/{published['id']}/versions").data if v["versionNo"] == 1)
    back = admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{first['id']}/rollback", {"reason": "Tarifa publicada por engano"}, format="json")
    assert back.status_code == 200 and back.data["current"]["id"] == first["id"]
    admin_client.put("/api/v1/system-parameters/quote.validity_days", {"value": 15, "rowVersion": 0, "reason": "Prazo comercial de quinze dias"}, format="json")
    short = admin_client.post(
        "/api/v1/quotes", {"proposerId": proposer["id"], "planId": medio["id"], "effectiveDate": "2026-07-01"}, format="json"
    ).data
    assert short["validUntil"] == "2026-07-16"

    # ----------------------------------------------------------------- 12. auditoria
    events = auditor.get("/api/v1/audit-events?size=200").data["items"]
    actions = {e["action"] for e in events}
    assert {"plan_benefit.configured", "quote.selection_updated", "quote.adjustment_applied", "quote.member_pre_existing_decided",
            "quote.scenario_created", "document.generated", "quote.renewal_created", "quote.capital_indexation_applied",
            "claims.imported", "claims.projection_run", "configuration.rolled_back", "system_parameter.updated"} <= actions
    assert all(e["metadata"].get("reason") for e in events if e["action"] in ("quote.adjustment_applied", "configuration.rolled_back"))

    # ------------------------------------------------------- 13. isolamento entre tenants
    from apps.foundation.infrastructure.models import Tenant

    other = Tenant.objects.create(id=uuid.uuid4(), code=f"other-{uuid.uuid4().hex[:6]}", name="Outro")
    stranger = make_client(tenant_id=other.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin q360.approve", actor_id="stranger")
    for url in (
        f"/api/v1/quotes/{quote['id']}", f"/api/v1/scenarios/{base['id']}", f"/api/v1/documents/{proposal.data['id']}/download",
        f"/api/v1/policies/{policy['id']}", f"/api/v1/quotes/{quote['id']}/requirements", f"/api/v1/claims/imports/{uuid.uuid4()}",
    ):
        assert stranger.get(url).status_code == 404, url
    assert stranger.get(f"/api/v1/claims/summary?proposerId={proposer['id']}").status_code == 400  # sem dados desse cliente
    assert stranger.get("/api/v1/benefits?size=200").data["page"]["totalElements"] >= 24  # catálogo próprio, não o do outro tenant
    assert stranger.get("/api/v1/quotes").data["items"] == []
    # o portal: a sessão do cliente não vê nada de outro tenant
    assert portal.get(f"/api/v1/customer-portal/plan-benefits?policyNumber=APO-NAO-EXISTE").status_code in (404, 400)
