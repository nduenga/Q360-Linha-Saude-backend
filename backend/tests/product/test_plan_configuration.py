"""Configuração de planos pelo GTE via API: definições do plano, capitais /
participação / carências por cobertura, validação global e modelos do PDF."""
from __future__ import annotations

import pytest

from apps.product.domain.market_templates import PARTICIPATION_OPTIONS

INDIVIDUAL = {
    "segment": "INDIVIDUAL_FAMILY",
    "tier": "MEDIUM",
    "accessSystem": "MIXED",
    "entryAge": {"min": 0, "max": 65},
    "permanenceAge": {"max": 75},
}


def _product(client, code="CFG-PROD"):
    return client.post("/api/v1/products", {"code": code, "name": code}).data


def _benefit(client, code):
    return next(
        i for i in client.get(f"/api/v1/benefits?q={code}&status=ALL&size=200").data["items"] if i["code"] == code
    )


def _plan(client, product, code="P1", settings=None, benefit_codes=()):
    ids = [_benefit(client, c)["id"] for c in benefit_codes]
    body = {"productId": product["id"], "code": code, "name": code, "complementaryBenefitIds": ids}
    if settings is not None:
        body["settings"] = settings
    return client.post("/api/v1/plans", body, format="json")


@pytest.mark.django_db
def test_create_plan_with_settings_and_read_them_back(admin_client):
    response = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL)
    assert response.status_code == 201
    assert response.data["settings"]["segment"] == "INDIVIDUAL_FAMILY"
    assert response.data["settings"]["noProRata"] is True
    assert admin_client.get(f"/api/v1/plans/{response.data['id']}").data["settings"]["entryAge"]["max"] == 65


@pytest.mark.django_db
def test_create_plan_rejects_invalid_settings(admin_client):
    product = _product(admin_client)
    bad = _plan(admin_client, product, settings={"segment": "INDIVIDUAL_FAMILY", "clinicalQuestionnaire": {"required": False}})
    assert bad.status_code == 400
    assert bad.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_patch_plan_settings_with_optimistic_locking(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    options = {**INDIVIDUAL, "participationOptions": PARTICIPATION_OPTIONS, "participationOption": "C"}
    updated = admin_client.patch(
        f"/api/v1/plans/{plan['id']}",
        {"name": plan["name"], "rowVersion": plan["rowVersion"], "settings": options},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["settings"]["participationOption"] == "C"

    # sem `settings` no corpo: não toca nas definições
    again = admin_client.patch(
        f"/api/v1/plans/{plan['id']}", {"name": "Novo nome", "rowVersion": updated.data["rowVersion"]}, format="json"
    )
    assert again.data["settings"]["participationOption"] == "C"

    stale = admin_client.patch(
        f"/api/v1/plans/{plan['id']}", {"name": "x", "rowVersion": plan["rowVersion"], "settings": options}, format="json"
    )
    assert stale.status_code == 409


@pytest.mark.django_db
def test_participation_options_rule_enforced_through_the_api(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    broken = [dict(o) for o in PARTICIPATION_OPTIONS]
    broken[2] = {**broken[2], "premiumAdjustmentPct": "10"}  # C mais cara que B
    resp = admin_client.patch(
        f"/api/v1/plans/{plan['id']}",
        {"name": "x", "rowVersion": plan["rowVersion"], "settings": {**INDIVIDUAL, "participationOptions": broken}},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_configure_coverage_capitals_participation_and_waiting(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    hospitalization = _benefit(admin_client, "HOSPITALIZATION")
    config = {
        "limits": [
            {"kind": "ANNUAL_PER_PERSON", "amount": "15000000"},
            {"kind": "PER_ACT_OR_DAY", "label": "Quarto por dia", "amount": "50000"},
        ],
        "participation": {
            "NETWORK": {"type": "NONE", "perEventDeductible": "100000"},
            "REIMBURSEMENT": {"type": "COINSURANCE", "insurerPct": "85", "insuredAnnualCap": "500000"},
        },
        "waitingDays": {"individual": 90, "group": 0, "scheduledSurgery": 180, "accidentWaived": True},
    }
    resp = admin_client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{hospitalization['id']}", {"configuration": config}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["configurationJson"]["limits"][0]["amount"] == "15000000"
    assert resp.data["configurationJson"]["inclusion"] == "INCLUDED"
    assert "warnings" in resp.data
    assert admin_client.get(f"/api/v1/plans/{plan['id']}/benefits/{hospitalization['id']}").data["configurationJson"]["waitingDays"]["scheduledSurgery"] == 180


@pytest.mark.django_db
def test_configure_attaches_optional_complementary_coverage(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    dental = _benefit(admin_client, "DENTAL")
    resp = admin_client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{dental['id']}",
        {"configuration": {"inclusion": "OPTIONAL", "limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "250000"}]}},
        format="json",
    )
    assert resp.status_code == 200
    attached = admin_client.get(f"/api/v1/plans/{plan['id']}/benefits").data
    dental_row = next(i for i in attached if i["benefit"]["code"] == "DENTAL")
    assert dental_row["configurationJson"]["inclusion"] == "OPTIONAL"


@pytest.mark.django_db
def test_configure_rejects_invalid_configurations(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    hospitalization = _benefit(admin_client, "HOSPITALIZATION")
    url = f"/api/v1/plans/{plan['id']}/benefits/{hospitalization['id']}"
    # BASE tem de estar incluída
    assert admin_client.put(url, {"configuration": {"inclusion": "OPTIONAL"}}, format="json").status_code == 400
    # sublimite acima do capital
    bad = {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "100"}, {"kind": "SUBLIMIT", "label": "x", "amount": "500"}]}
    assert admin_client.put(url, {"configuration": bad}, format="json").status_code == 400
    # moeda USD não permitida na hospitalização
    assert admin_client.put(url, {"configuration": {"currency": "USD"}}, format="json").status_code == 400


@pytest.mark.django_db
def test_inactive_coverage_cannot_be_newly_configured_on_a_plan(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    vaccination = _benefit(admin_client, "VACCINATION")
    admin_client.post(f"/api/v1/benefits/{vaccination['id']}/deactivate", {"reason": "Descontinuada por teste"}, format="json")
    resp = admin_client.put(f"/api/v1/plans/{plan['id']}/benefits/{vaccination['id']}", {"configuration": {}}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_plan_validation_reports_errors_and_warnings(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    report = admin_client.get(f"/api/v1/plans/{plan['id']}/validation").data
    assert report["valid"] is False
    assert "HOSPITALIZATION_CAPITAL" in {e["code"] for e in report["errors"]}
    assert "NETWORK_COVERAGE" in {w["code"] for w in report["warnings"]}

    hospitalization = _benefit(admin_client, "HOSPITALIZATION")
    admin_client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{hospitalization['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "5000000"}]}},
        format="json",
    )
    assert admin_client.get(f"/api/v1/plans/{plan['id']}/validation").data["valid"] is True


@pytest.mark.django_db
def test_changing_settings_can_invalidate_existing_coverage_config(admin_client):
    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    outpatient = _benefit(admin_client, "OUTPATIENT")
    admin_client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{outpatient['id']}",
        {"configuration": {"limits": [{"kind": "HOUSEHOLD_SHARED", "amount": "3000000"}]}},
        format="json",
    )
    group = {"segment": "GROUP", "group": {"minInsured": 5, "adhesion": "MANDATORY"}}
    admin_client.patch(
        f"/api/v1/plans/{plan['id']}", {"name": "x", "rowVersion": plan["rowVersion"], "settings": group}, format="json"
    )
    report = admin_client.get(f"/api/v1/plans/{plan['id']}/validation").data
    assert any(e["scope"] == "coverage.OUTPATIENT" for e in report["errors"])


@pytest.mark.django_db
def test_group_categories_with_same_coverages_are_not_duplicates(admin_client):
    """PDF: Grupo tem 2–3 planos por categoria (Colaboradores/Quadros/
    Administração) com as mesmas coberturas e capitais diferentes."""
    product = _product(admin_client, "GRP-CAT")
    base = {"segment": "GROUP", "group": {"minInsured": 5, "adhesion": "MANDATORY"}}
    for category in ("Colaboradores", "Quadros", "Administração"):
        resp = _plan(admin_client, product, code=category[:4].upper(), settings={**base, "category": category})
        assert resp.status_code == 201, resp.data
    dup = _plan(admin_client, product, code="DUP", settings={**base, "category": "Quadros"})
    assert dup.status_code == 409


@pytest.mark.django_db
def test_load_pdf_market_templates(admin_client):
    result = admin_client.post("/api/v1/product-templates/market", {}, format="json")
    assert result.status_code == 200
    assert set(result.data["createdProducts"]) == {"SAUDE-INDIVIDUAL", "SAUDE-GRUPO"}
    assert set(result.data["createdPlans"]) == {
        "IND-BASE", "IND-MEDIO", "IND-SUPERIOR", "GRP-COLABORADORES", "GRP-QUADROS", "GRP-ADMINISTRACAO",
    }
    assert result.data["indicative"] is True
    assert all(report["valid"] for report in result.data["plans"]), result.data["plans"]

    # Cada plano ficou com a configuração do PDF
    plans = {p["code"]: p for p in admin_client.get("/api/v1/plans?size=50").data["items"]}
    medio = plans["IND-MEDIO"]
    assert medio["settings"]["participationOption"] == "B"
    assert [o["code"] for o in medio["settings"]["participationOptions"]] == ["A", "B", "C", "D", "E"]
    rows = {r["benefit"]["code"]: r["configurationJson"] for r in admin_client.get(f"/api/v1/plans/{medio['id']}/benefits").data}
    assert rows["HOSPITALIZATION"]["limits"][0] == {"kind": "ANNUAL_PER_PERSON", "amount": "15000000"}
    assert rows["MEDICAL_EVACUATION"]["inclusion"] == "OPTIONAL"
    assert rows["MEDICAL_EVACUATION"]["requiresPriorApproval"] is True
    assert rows["PHYSIOTHERAPY"]["limits"][0]["count"] == 20

    # Idempotente: nada é recriado nem sobrescrito
    again = admin_client.post("/api/v1/product-templates/market", {}, format="json").data
    assert again["createdPlans"] == [] and again["createdProducts"] == []
    assert len(again["skippedPlans"]) == 6


@pytest.mark.django_db
def test_template_plans_keep_gte_edits_when_reloaded(admin_client):
    admin_client.post("/api/v1/product-templates/market", {}, format="json")
    plans = {p["code"]: p for p in admin_client.get("/api/v1/plans?size=50").data["items"]}
    base = plans["IND-BASE"]
    hospitalization = _benefit(admin_client, "HOSPITALIZATION")
    admin_client.put(
        f"/api/v1/plans/{base['id']}/benefits/{hospitalization['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "7000000"}]}},
        format="json",
    )
    admin_client.post("/api/v1/product-templates/market", {}, format="json")
    row = admin_client.get(f"/api/v1/plans/{base['id']}/benefits/{hospitalization['id']}").data
    assert row["configurationJson"]["limits"][0]["amount"] == "7000000"


@pytest.mark.django_db
def test_only_product_managers_can_configure(tenant):
    from tests.product.conftest import make_client

    admin = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
    plan = _plan(admin, _product(admin), settings=INDIVIDUAL).data
    hospitalization = _benefit(admin, "HOSPITALIZATION")
    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write")
    url = f"/api/v1/plans/{plan['id']}/benefits/{hospitalization['id']}"
    assert subscriber.put(url, {"configuration": {}}, format="json").status_code == 403
    assert subscriber.get(f"/api/v1/plans/{plan['id']}/validation").status_code == 200
    assert subscriber.post("/api/v1/product-templates/market", {}, format="json").status_code == 403


@pytest.mark.django_db
def test_configuration_changes_are_audited(admin_client, tenant):
    from tests.product.conftest import make_client

    plan = _plan(admin_client, _product(admin_client), settings=INDIVIDUAL).data
    hospitalization = _benefit(admin_client, "HOSPITALIZATION")
    admin_client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{hospitalization['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "9000000"}]}},
        format="json",
    )
    auditor = make_client(tenant_id=tenant.id, roles=[], scope="q360.read q360.audit")
    events = auditor.get("/api/v1/audit-events?action=plan_benefit.configured").data["items"]
    assert events and events[0]["metadata"]["after"]["limits"][0]["amount"] == "9000000"
    assert events[0]["metadata"]["benefitCode"] == "HOSPITALIZATION"
