"""R1 — versões da cotação (guardar, comparar, restaurar), cópia e requisitos
de subscrição do PDF (idades, agregado, dimensão do grupo, questionário
clínico, exames, pré-autorização, carências, exclusões)."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_quote_simulator import _benefit, _quote, _scope, _total

REASON = "Motivo de teste suficiente"


def _versions(client, scope):
    return client.get(f"/api/v1/quotes/{scope['quoteId']}/versions").data


def _adjust(client, scope, **body):
    resp = client.post(f"/api/v1/quotes/{scope['quoteId']}/adjustments", {"reason": "Ajuste de teste auditável", **body}, format="json")
    assert resp.status_code == 201, resp.data
    return resp.data


# -------------------------------------------------------------------- versions
@pytest.mark.django_db
def test_pricing_creates_a_version_only_when_the_state_changed(admin_client):
    scope = _scope(admin_client)
    versions = _versions(admin_client, scope)
    assert [(v["versionNo"], v["source"], v["totalAmount"]) for v in versions] == [(1, "PRICED", "200.00")]

    # recalcular sem alterar nada não cria versão
    admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/price", {"recalculate": True}, format="json")
    assert len(_versions(admin_client, scope)) == 1

    _adjust(admin_client, scope, kind="SURCHARGE_PERCENT", value="10")
    versions = _versions(admin_client, scope)
    assert [(v["versionNo"], v["totalAmount"]) for v in versions] == [(2, "220.00"), (1, "200.00")]


@pytest.mark.django_db
def test_manual_version_needs_a_reason_and_is_always_saved(admin_client):
    scope = _scope(admin_client)
    url = f"/api/v1/quotes/{scope['quoteId']}/versions"
    assert admin_client.post(url, {"reason": "x"}, format="json").status_code == 400
    saved = admin_client.post(url, {"reason": "Antes de falar com o cliente"}, format="json")
    assert saved.status_code == 201
    assert saved.data["versionNo"] == 2 and saved.data["source"] == "MANUAL" and saved.data["reason"] == "Antes de falar com o cliente"
    detail = admin_client.get(f"{url}/2").data
    assert detail["snapshot"]["effectiveDate"] == "2026-06-01"
    assert len(detail["snapshot"]["members"]) == 2 and len(detail["checksum"]) == 64
    assert admin_client.get(f"{url}/99").status_code == 404


@pytest.mark.django_db
def test_diff_between_versions_and_against_the_current_state(admin_client):
    scope = _scope(admin_client)
    _adjust(admin_client, scope, kind="SURCHARGE_PERCENT", value="10")
    admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/selection",
        {"selection": {"participationOption": "C"}, "rowVersion": _quote(admin_client, scope)["rowVersion"]},
        format="json",
    )
    url = f"/api/v1/quotes/{scope['quoteId']}/versions"
    diff = admin_client.get(f"{url}/1/diff?against=2").data
    fields = {c["field"] for c in diff["changes"]}
    assert {"adjustments", "pricing.totalAmount"} <= fields
    total_change = next(c for c in diff["changes"] if c["field"] == "pricing.totalAmount")
    assert total_change == {"field": "pricing.totalAmount", "before": "200.00", "after": "220.00"}

    current = admin_client.get(f"{url}/1/diff").data
    assert current["against"] == "current"
    assert any(c["field"] == "selection.participationOption" and c["after"] == "C" for c in current["changes"])
    same = admin_client.get(f"{url}/2/diff?against=2").data
    assert same["changes"] == []


@pytest.mark.django_db
def test_restore_a_version_returns_the_quote_to_that_state(admin_client):
    scope = _scope(admin_client)
    first = scope["memberIds"][0]
    admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/selection",
        {"selection": {"participationOption": "A", "optionalBenefitCodes": ["DENTAL"]}, "rowVersion": _quote(admin_client, scope)["rowVersion"]},
        format="json",
    )
    _adjust(admin_client, scope, kind="SURCHARGE_PERCENT", value="10")
    admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/members/{first}/pre-existing",
        {"decision": {"mode": "TOTAL_EXCLUSION"}, "reason": "Exclusão total declarada"},
        format="json",
    )
    total_now = _total(admin_client, scope)
    assert total_now != Decimal("200.00")

    url = f"/api/v1/quotes/{scope['quoteId']}/versions"
    assert admin_client.post(f"{url}/1/restore", {"reason": "x"}, format="json").status_code == 400
    restored = admin_client.post(f"{url}/1/restore", {"reason": "O cliente voltou à proposta inicial"}, format="json")
    assert restored.status_code == 200, restored.data
    assert restored.data["quote"]["status"] == "READY"
    assert restored.data["quote"]["selection"] == {}
    assert _total(admin_client, scope) == Decimal("200.00")
    adjustments = admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/adjustments").data
    assert [a["status"] for a in adjustments] == ["REMOVED"]
    assert "Restauro da versão 1" in adjustments[0]["removedReason"]
    members = {m["memberId"]: m for m in admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/members").data["items"]}
    assert members[first]["preExisting"] == {}

    versions = _versions(admin_client, scope)
    assert versions[0]["source"] == "RESTORED" and versions[0]["versionNo"] == restored.data["newVersionNo"]
    # o histórico nunca é reescrito: as versões antigas continuam lá
    assert {v["versionNo"] for v in versions} >= {1, 2, 3, 4}


@pytest.mark.django_db
def test_restore_also_restores_the_population(admin_client):
    scope = _scope(admin_client, members=2)
    admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/versions", {"reason": "Com os dois membros"}, format="json")
    removed = scope["memberIds"][1]
    assert admin_client.delete(f"/api/v1/quotes/{scope['quoteId']}/members/{removed}").status_code == 204
    admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/price")
    assert _total(admin_client, scope) == Decimal("100.00")

    restored = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/versions/2/restore", {"reason": "Voltar a incluir o 2.º membro"}, format="json")
    assert restored.status_code == 200, restored.data
    assert restored.data["addedMembers"] == [removed] and restored.data["removedMembers"] == []
    assert _total(admin_client, scope) == Decimal("200.00")


@pytest.mark.django_db
def test_restore_is_blocked_when_the_quote_is_no_longer_editable(admin_client):
    scope = _scope(admin_client)
    quote = _quote(admin_client, scope)
    admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/cancel", {"reasonCode": "T", "reasonText": "t", "rowVersion": quote["rowVersion"]}, format="json")
    resp = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/versions/1/restore", {"reason": REASON}, format="json")
    assert resp.status_code == 409 and resp.data["code"] == "QUOTE-STATE"


# ----------------------------------------------------------------------- clone
@pytest.mark.django_db
def test_clone_copies_population_selection_adjustments_and_pre_existing(admin_client):
    scope = _scope(admin_client)
    first = scope["memberIds"][0]
    admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/selection",
        {"selection": {"participationOption": "C", "optionalBenefitCodes": ["DENTAL"]}, "rowVersion": _quote(admin_client, scope)["rowVersion"]},
        format="json",
    )
    _adjust(admin_client, scope, kind="DISCOUNT_PERCENT", value="5")
    admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/members/{first}/pre-existing",
        {"decision": {"mode": "TOTAL_EXCLUSION"}, "reason": "Exclusão total declarada"},
        format="json",
    )
    original = _quote(admin_client, scope)

    assert admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/clone", {"reason": "x"}, format="json").status_code == 400
    cloned = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/clone", {"reason": "Variante para o cliente"}, format="json")
    assert cloned.status_code == 201, cloned.data
    copy = cloned.data
    assert copy["id"] != original["id"] and copy["quoteNumber"] != original["quoteNumber"]
    assert copy["status"] == "READY" and copy["selection"] == original["selection"]
    assert copy["effectiveDate"] == original["effectiveDate"]

    copy_scope = {"quoteId": copy["id"]}
    assert _total(admin_client, copy_scope) == _total(admin_client, scope) == Decimal("195.70")  # ((100 * 0.93) + 10) * 0.95 * 2
    assert len(admin_client.get(f"/api/v1/quotes/{copy['id']}/members").data["items"]) == 2
    assert [a["kind"] for a in admin_client.get(f"/api/v1/quotes/{copy['id']}/adjustments").data] == ["DISCOUNT_PERCENT"]
    copy_members = {m["memberId"]: m for m in admin_client.get(f"/api/v1/quotes/{copy['id']}/members").data["items"]}
    assert copy_members[first]["preExisting"]["mode"] == "TOTAL_EXCLUSION"
    assert _versions(admin_client, copy_scope)[0]["source"] == "CLONE"

    # a cópia é independente
    _adjust(admin_client, copy_scope, kind="SURCHARGE_PERCENT", value="10")
    assert _total(admin_client, scope) == Decimal("195.70")


@pytest.mark.django_db
def test_clone_with_a_different_effective_date(admin_client):
    scope = _scope(admin_client)
    cloned = admin_client.post(
        f"/api/v1/quotes/{scope['quoteId']}/clone", {"reason": "Mesma proposta para o mês seguinte", "effectiveDate": "2026-07-01"}, format="json"
    )
    assert cloned.status_code == 201 and cloned.data["effectiveDate"] == "2026-07-01" and cloned.data["validUntil"] == "2026-07-31"


# --------------------------------------------------------------- requirements
INDIVIDUAL = {
    "segment": "INDIVIDUAL_FAMILY",
    "tier": "MEDIUM",
    "accessSystem": "MIXED",
    "entryAge": {"min": 0, "max": 65},
    "permanenceAge": {"max": 75},
    "household": {"spouse": True, "dependentChildMaxAge": 25},
    "clinicalQuestionnaire": {"required": True, "medicalExamAboveAge": 55, "medicalExamAboveCapital": "10000000"},
    "priorAuthorization": {"internments": True, "highCostExams": True, "scheduledSurgeries": True},
    "network": {"regions": ["LUANDA"]},
}


def _member(client, scope, *, date_of_birth, relationship="TITULAR"):
    member_id = client.post(
        "/api/v1/members",
        {"proposerId": scope["proposerId"], "relationshipCode": relationship, "dateOfBirth": date_of_birth},
    ).data["id"]
    client.post(f"/api/v1/quotes/{scope['quoteId']}/members", {"memberId": member_id}, format="json")
    client.post(f"/api/v1/quotes/{scope['quoteId']}/price", {"recalculate": True}, format="json")
    return member_id


def _requirements(client, scope):
    return client.get(f"/api/v1/quotes/{scope['quoteId']}/requirements").data


def _codes(items):
    return {i["code"] for i in items}


@pytest.mark.django_db
def test_individual_requirements_questionnaire_exam_prior_authorization_and_exclusions(admin_client):
    by_age_only = {**INDIVIDUAL, "clinicalQuestionnaire": {"required": True, "medicalExamAboveAge": 55}}
    scope = _scope(admin_client, settings=by_age_only)
    older = _member(admin_client, scope, date_of_birth="1969-01-01")  # 57 anos em 2026-06-01
    result = _requirements(admin_client, scope)

    assert result["segment"] == "INDIVIDUAL_FAMILY" and result["blocking"] is False
    assert "CLINICAL_QUESTIONNAIRE_REQUIRED" in _codes(result["warnings"])
    exam = next(w for w in result["warnings"] if w["code"] == "MEDICAL_EXAM_REQUIRED")
    assert exam["memberId"] == older and "idade 57" in exam["message"]
    assert result["members"][older]["medicalExamRequired"] is True
    assert result["members"][scope["memberIds"][0]]["medicalExamRequired"] is False  # 36 anos
    assert result["members"][scope["memberIds"][0]]["clinicalQuestionnaireRequired"] is True

    prior = next(i for i in result["info"] if i["code"] == "PRIOR_AUTHORIZATION")
    assert prior["appliesTo"] == ["internments", "highCostExams", "scheduledSurgeries"]
    assert "NETWORK_COVERAGE" not in _codes(result["warnings"])  # regiões definidas

    exclusion_codes = {e["code"] for e in result["exclusions"]}
    assert {"AESTHETIC_SURGERY", "INFERTILITY", "HIGH_RISK_SPORTS", "WORK_TRAFFIC_ACCIDENTS", "ABROAD_WITHOUT_APPROVAL", "LONG_TERM_CARE"} <= exclusion_codes
    assert len(result["exclusions"]) >= 13


@pytest.mark.django_db
def test_exam_required_above_a_capital(admin_client):
    scope = _scope(admin_client, settings={**INDIVIDUAL, "clinicalQuestionnaire": {"required": True, "medicalExamAboveCapital": "10000000"}})
    result = _requirements(admin_client, scope)  # capital de hospitalização do plano = 15.000.000
    assert result["members"][scope["memberIds"][0]]["medicalExamRequired"] is True
    assert "capital" in next(w for w in result["warnings"] if w["code"] == "MEDICAL_EXAM_REQUIRED")["message"]


@pytest.mark.django_db
def test_age_outside_entry_range_blocks_submission(admin_client):
    scope = _scope(admin_client, settings=INDIVIDUAL)
    too_old = _member(admin_client, scope, date_of_birth="1950-01-01")  # 76 anos
    result = _requirements(admin_client, scope)
    assert result["blocking"] is True
    error = next(e for e in result["errors"] if e["code"] == "AGE_OUT_OF_ENTRY_RANGE")
    assert error["memberId"] == too_old and error["age"] == 76

    quote = _quote(admin_client, scope)
    blocked = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/submit", {"rowVersion": quote["rowVersion"]}, format="json")
    assert blocked.status_code == 400 and "entrada" in blocked.data["detail"]
    # remover a pessoa resolve
    admin_client.delete(f"/api/v1/quotes/{scope['quoteId']}/members/{too_old}")
    admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/price", {"recalculate": True}, format="json")
    quote = _quote(admin_client, scope)
    ok = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/submit", {"rowVersion": quote["rowVersion"]}, format="json")
    assert ok.status_code == 200


@pytest.mark.django_db
def test_household_rules_spouse_and_dependent_child_age(admin_client):
    settings = {**INDIVIDUAL, "household": {"spouse": False, "dependentChildMaxAge": 25}}
    scope = _scope(admin_client, settings=settings)
    spouse = _member(admin_client, scope, date_of_birth="1992-01-01", relationship="CONJUGE")
    old_child = _member(admin_client, scope, date_of_birth="1999-01-01", relationship="FILHO")  # 27 anos
    young_child = _member(admin_client, scope, date_of_birth="2008-01-01", relationship="FILHO")  # 18 anos
    errors = {(e["code"], e["memberId"]) for e in _requirements(admin_client, scope)["errors"]}
    assert ("SPOUSE_NOT_ALLOWED", spouse) in errors
    assert ("CHILD_AGE_LIMIT", old_child) in errors
    assert not any(member == young_child for _, member in errors)


@pytest.mark.django_db
def test_group_minimum_size_blocks_submission(admin_client):
    group = {"segment": "GROUP", "tier": "CUSTOM", "category": "Quadros", "accessSystem": "MIXED",
             "group": {"minInsured": 5, "adhesion": "MANDATORY", "questionnaireWaivedAboveInsured": 20,
                       "profitSharing": {"lossRatioThresholdPct": "65"}, "monthlyInclusionsExclusions": True}}
    scope = _scope(admin_client, settings=group, members=2)
    result = _requirements(admin_client, scope)
    assert result["blocking"] is True
    error = next(e for e in result["errors"] if e["code"] == "GROUP_MIN_SIZE")
    assert error["insured"] == 2 and error["minimum"] == 5 and "individual" in error["message"]
    assert {"PROFIT_SHARING", "MONTHLY_MOVEMENTS", "CLAIMS_HISTORY_ON_TRANSFER"} <= _codes(result["info"])
    assert "65" in next(i for i in result["info"] if i["code"] == "PROFIT_SHARING")["message"]
    assert next(i for i in result["info"] if i["code"] == "CLAIMS_HISTORY_ON_TRANSFER")["satisfied"] is False
    quote = _quote(admin_client, scope)
    assert admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/submit", {"rowVersion": quote["rowVersion"]}, format="json").status_code == 400

    for index in range(3):
        _member(admin_client, scope, date_of_birth=f"198{index}-03-01")
    assert _requirements(admin_client, scope)["blocking"] is False  # 5 pessoas


@pytest.mark.django_db
def test_group_questionnaire_waived_for_mandatory_adhesion_above_the_threshold(admin_client):
    base = {"segment": "GROUP", "tier": "CUSTOM", "accessSystem": "MIXED"}
    mandatory = {**base, "group": {"minInsured": 1, "adhesion": "MANDATORY", "questionnaireWaivedAboveInsured": 2}}
    scope = _scope(admin_client, settings=mandatory, members=3)
    assert _requirements(admin_client, scope)["members"][scope["memberIds"][0]]["clinicalQuestionnaireRequired"] is False
    assert "CLINICAL_QUESTIONNAIRE_REQUIRED" not in _codes(_requirements(admin_client, scope)["warnings"])


@pytest.mark.django_db
def test_group_questionnaire_required_with_optional_adhesion(admin_client, tenant):
    optional = {"segment": "GROUP", "tier": "CUSTOM", "accessSystem": "MIXED", "group": {"minInsured": 1, "adhesion": "OPTIONAL"}}
    scope = _scope(admin_client, settings=optional, members=3)
    assert _requirements(admin_client, scope)["members"][scope["memberIds"][0]]["clinicalQuestionnaireRequired"] is True


@pytest.mark.django_db
def test_waiting_periods_evacuation_terms_and_network_warning(admin_client):
    settings = {k: v for k, v in INDIVIDUAL.items() if k != "network"} | {"waitingRules": {"accidentWaived": True}}
    scope = _scope(admin_client, settings=settings)
    benefit = _benefit(admin_client, "MEDICAL_EVACUATION")
    admin_client.put(
        f"/api/v1/plans/{scope['planId']}/benefits/{benefit['id']}",
        {"configuration": {"inclusion": "INCLUDED", "currency": "USD", "destinations": ["Portugal", "Brasil"],
                           "limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "100000"}], "waitingDays": {"individual": 180}}},
        format="json",
    )
    hospital = _benefit(admin_client, "HOSPITALIZATION")
    admin_client.put(
        f"/api/v1/plans/{scope['planId']}/benefits/{hospital['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "15000000"}], "waitingDays": {"individual": 90, "scheduledSurgery": 180, "accidentWaived": True}}},
        format="json",
    )
    result = _requirements(admin_client, scope)
    assert "NETWORK_COVERAGE" in _codes(result["warnings"])
    terms = next(i for i in result["info"] if i["code"] == "EVACUATION_TERMS")
    assert terms["destinations"] == ["Portugal", "Brasil"] and terms["currency"] == "USD" and "risco cambial" in terms["message"]
    waiting = {w["coverage"]: w for w in result["waitingPeriods"]}
    assert waiting["HOSPITALIZATION"] == {"coverage": "HOSPITALIZATION", "days": 90, "scheduledSurgeryDays": 180, "accidentWaived": True}
    assert waiting["MEDICAL_EVACUATION"]["days"] == 180


@pytest.mark.django_db
def test_plans_without_settings_have_no_blocking_rules(admin_client):
    scope = _scope(admin_client, settings={})
    result = _requirements(admin_client, scope)
    assert result["blocking"] is False and result["errors"] == []
    quote = _quote(admin_client, scope)
    assert admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/submit", {"rowVersion": quote["rowVersion"]}, format="json").status_code == 200


@pytest.mark.django_db
def test_requirements_readable_by_auditors(admin_client, tenant):
    scope = _scope(admin_client, settings=INDIVIDUAL)
    reader = make_client(tenant_id=tenant.id, roles=["AUDITOR"], scope="q360.read q360.audit")
    assert reader.get(f"/api/v1/quotes/{scope['quoteId']}/requirements").status_code == 200
    assert reader.post(f"/api/v1/quotes/{scope['quoteId']}/versions", {"reason": REASON}, format="json").status_code == 403
    assert reader.post(f"/api/v1/quotes/{scope['quoteId']}/clone", {"reason": REASON}, format="json").status_code == 403
    assert json.dumps(reader.get(f"/api/v1/quotes/{scope['quoteId']}/versions").data)


@pytest.mark.django_db
def test_quote_numbers_stay_unique_across_effective_years(admin_client):
    """Regression: the counter used to reset per effective year while
    `uq_quote_number` is unique per tenant, so the first quote with an
    effective date in a new year (every renewal!) collided with COT-1."""
    scope = _scope(admin_client)
    first = _quote(admin_client, scope)["quoteNumber"]
    numbers = {first}
    for effective in ("2027-01-15", "2027-02-01", "2026-09-01", "2028-01-01"):
        created = admin_client.post(
            "/api/v1/quotes", {"proposerId": scope["proposerId"], "planId": scope["planId"], "effectiveDate": effective}, format="json"
        )
        assert created.status_code == 201, created.data
        numbers.add(created.data["quoteNumber"])
    assert len(numbers) == 5
