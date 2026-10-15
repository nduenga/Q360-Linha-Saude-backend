"""R1 — proposta de renovação de uma apólice, com as regras do PDF: renovação
até à idade de permanência do plano (70–75) e revisão de capitais face à
inflação dos custos médicos em cada renovação."""
from __future__ import annotations

import datetime

import pytest

from tests.policy.test_coverage_api import _activate
from tests.policy.test_issuance import _SIGN_BODY, _approved_quote, _approver

REASON = "Motivo de teste suficiente"


def _plan_of(client, policy):
    plans = client.get("/api/v1/plans?size=50").data["items"]
    return next(p for p in plans if p["id"] == client.get(f"/api/v1/policies/{policy['id']}").data["planId"])


def _configure_plan(client, policy, *, settings, hospital_capital="15000000"):
    plan = _plan_of(client, policy)
    updated = client.patch(
        f"/api/v1/plans/{plan['id']}", {"name": plan["name"], "rowVersion": plan["rowVersion"], "settings": settings}, format="json"
    )
    assert updated.status_code == 200, updated.data
    hospital = next(i for i in client.get("/api/v1/benefits?q=HOSPITALIZATION&size=200").data["items"] if i["code"] == "HOSPITALIZATION")
    client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{hospital['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": hospital_capital}]}},
        format="json",
    )
    return plan


SETTINGS = {
    "segment": "INDIVIDUAL_FAMILY",
    "accessSystem": "MIXED",
    "entryAge": {"min": 0, "max": 65},
    "permanenceAge": {"max": 75},
    "capitalIndexation": {"medicalInflationPct": "10", "reviewOnRenewal": True},
}


@pytest.mark.django_db
def test_renewal_quote_from_an_active_policy(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="R1")
    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json")
    assert renewal.status_code == 201, renewal.data
    body = renewal.data
    end = datetime.date.fromisoformat(policy["endDate"])
    assert body["quoteType"] == "RENEWAL" and body["sourcePolicyId"] == policy["id"]
    # A cotação de renovação não tem data de efeito; o novo período proposto começa a seguir ao fim do actual.
    assert "effectiveDate" not in body
    assert body["renewal"]["proposedStartDate"] == (end + datetime.timedelta(days=1)).isoformat()
    assert body["status"] == "READY"  # população carregada e preço calculado
    context = body["renewal"]
    assert context["sourcePolicyNumber"] == policy["policyNumber"]
    assert context["previousPeriod"] == {"start": policy["startDate"], "end": policy["endDate"]}
    assert context["previousPremium"]["amount"] == "1200.00"
    assert context["carriedMembers"] == [policy["memberId"]] and context["skippedMembers"] == []
    assert context["capitalIndexation"]["applied"] is False

    members = admin_client.get(f"/api/v1/quotes/{body['id']}/members").data["items"]
    assert [m["memberId"] for m in members] == [policy["memberId"]]
    versions = admin_client.get(f"/api/v1/quotes/{body['id']}/versions").data
    assert versions[0]["source"] == "RENEWAL" and "Renovação da apólice" in versions[0]["reason"]

    listed = admin_client.get(f"/api/v1/quotes?quoteType=RENEWAL&sourcePolicyId={policy['id']}").data["items"]
    assert [q["id"] for q in listed] == [body["id"]]


@pytest.mark.django_db
def test_only_one_open_renewal_per_policy(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="R2")
    first = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json").data
    again = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json")
    assert again.status_code == 409 and again.data["code"] == "QUOTE-STATE"
    quote = admin_client.get(f"/api/v1/quotes/{first['id']}").data
    admin_client.post(f"/api/v1/quotes/{first['id']}/cancel", {"reasonCode": "T", "reasonText": "t", "rowVersion": quote["rowVersion"]}, format="json")
    assert admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json").status_code == 201


@pytest.mark.django_db
def test_renewal_of_an_unknown_policy_is_a_400(admin_client):
    import uuid

    assert admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": str(uuid.uuid4())}, format="json").status_code == 400


@pytest.mark.django_db
def test_a_policy_still_awaiting_its_first_premium_cannot_be_renewed(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="R3")
    pending = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy", {**_SIGN_BODY, "signedAt": "2026-06-10T14:00:00Z", "rowVersion": quote["rowVersion"]}, format="json"
    ).data
    assert pending["status"] == "PENDING_FIRST_PREMIUM"
    resp = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": pending["id"]}, format="json")
    assert resp.status_code == 409


@pytest.mark.django_db
def test_the_emission_form_proposes_the_day_after_the_current_period(admin_client, tenant):
    """Antes, a renovação recebia uma data de efeito que não podia ser anterior
    ao fim do período. A cotação deixou de ter essa data (2026-10-15): o
    início é escolhido na emissão e o formulário propõe o dia seguinte ao fim
    do período actual."""
    active = _activate(admin_client, tenant, suffix="R4")
    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": active["id"]}, format="json")
    assert renewal.status_code == 201, renewal.data
    draft = admin_client.get(f"/api/v1/quotes/{renewal.data['id']}/policy-draft")
    assert draft.status_code == 200, draft.data
    expected = (datetime.date.fromisoformat(active["endDate"]) + datetime.timedelta(days=1)).isoformat()
    assert str(draft.data["defaults"]["requestedStartDate"]) == expected


@pytest.mark.django_db
def test_people_above_the_permanence_age_are_not_renewed(admin_client, tenant):
    """PDF: a idade de entrada costuma ir até aos 60–65, com renovação até aos 70–75."""
    policy = _activate(admin_client, tenant, suffix="R5")  # titular nascido em 1990 -> 37 anos em 2027
    _configure_plan(admin_client, policy, settings={**SETTINGS, "entryAge": {"min": 0, "max": 30}, "permanenceAge": {"max": 30}})
    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json")
    assert renewal.status_code == 201
    context = renewal.data["renewal"]
    assert context["carriedMembers"] == []
    assert context["skippedMembers"] == [{"memberId": policy["memberId"], "reason": "PERMANENCE_AGE_EXCEEDED", "age": "37", "limit": "30"}]
    assert admin_client.get(f"/api/v1/quotes/{renewal.data['id']}/members").data["items"] == []
    assert renewal.data["status"] == "DRAFT"  # sem pessoas não há prémio


@pytest.mark.django_db
def test_renewal_requirements_ask_to_review_the_capitals(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="R6")
    _configure_plan(admin_client, policy, settings=SETTINGS)
    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json").data
    result = admin_client.get(f"/api/v1/quotes/{renewal['id']}/requirements").data
    warning = next(w for w in result["warnings"] if w["code"] == "CAPITAL_INDEXATION_PENDING")
    assert "inflação" in warning["message"]
    assert renewal["renewal"]["capitalIndexation"]["medicalInflationPct"] == "10"


@pytest.mark.django_db
def test_capital_indexation_dry_run_apply_and_rules(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="R7")
    _configure_plan(admin_client, policy, settings=SETTINGS)
    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json").data
    url = f"/api/v1/quotes/{renewal['id']}/renewal/indexation"

    dry = admin_client.post(f"{url}?dryRun=true", {"reason": REASON}, format="json")
    assert dry.status_code == 200, dry.data
    assert dry.data["dryRun"] is True and dry.data["medicalInflationPct"] == "10"  # a do plano, por omissão
    assert dry.data["coverages"]["HOSPITALIZATION"][0] == {"kind": "ANNUAL_PER_PERSON", "amount": "16500000"}
    assert set(dry.data["impact"]) == {"previousTotal", "newTotal", "delta", "deltaPercent", "currencyCode"}
    assert admin_client.get(f"/api/v1/quotes/{renewal['id']}").data["selection"] == {}  # nada gravado

    assert admin_client.post(url, {"reason": "x"}, format="json").status_code == 400
    assert admin_client.post(url, {"medicalInflationPct": "-5", "reason": REASON}, format="json").status_code == 400

    explicit = admin_client.post(f"{url}?dryRun=true", {"medicalInflationPct": "20", "roundTo": "1000000", "reason": REASON}, format="json")
    assert explicit.data["coverages"]["HOSPITALIZATION"][0]["amount"] == "18000000"
    rounded = admin_client.post(f"{url}?dryRun=true", {"roundTo": "1000000", "reason": REASON}, format="json")
    assert rounded.data["coverages"]["HOSPITALIZATION"][0]["amount"] == "17000000"  # 16,5M arredondado

    applied = admin_client.post(url, {"reason": "Revisão anual dos capitais"}, format="json")
    assert applied.status_code == 200, applied.data
    quote = applied.data["quote"]
    assert quote["selection"]["coverageOverrides"]["HOSPITALIZATION"]["limits"][0]["amount"] == "16500000"
    assert quote["renewal"]["capitalIndexation"] == {"medicalInflationPct": "10", "applied": True, "reason": "Revisão anual dos capitais"}
    assert quote["status"] == "READY"
    result = admin_client.get(f"/api/v1/quotes/{renewal['id']}/requirements").data
    assert "CAPITAL_INDEXATION_PENDING" not in {w["code"] for w in result["warnings"]}
    # o plano real não mudou
    plan = _plan_of(admin_client, policy)
    hospital = next(i for i in admin_client.get("/api/v1/benefits?q=HOSPITALIZATION&size=200").data["items"] if i["code"] == "HOSPITALIZATION")
    assert admin_client.get(f"/api/v1/plans/{plan['id']}/benefits/{hospital['id']}").data["configurationJson"]["limits"][0]["amount"] == "15000000"


@pytest.mark.django_db
def test_indexation_only_applies_to_renewal_quotes_and_needs_a_percentage(admin_client, tenant):
    policy = _activate(admin_client, tenant, suffix="R8")
    new_quote = admin_client.get(f"/api/v1/policies/{policy['id']}").data["sourceQuoteId"]
    resp = admin_client.post(f"/api/v1/quotes/{new_quote}/renewal/indexation", {"medicalInflationPct": "5", "reason": REASON}, format="json")
    assert resp.status_code == 409 and resp.data["code"] == "QUOTE-STATE"

    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json").data
    no_pct = admin_client.post(f"/api/v1/quotes/{renewal['id']}/renewal/indexation", {"reason": REASON}, format="json")
    assert no_pct.status_code == 400  # o plano não define a percentagem e não foi indicada


@pytest.mark.django_db
def test_renewal_requires_quote_create_permission(admin_client, tenant):
    from tests.policy.conftest import make_client

    policy = _activate(admin_client, tenant, suffix="R9")
    reader = make_client(tenant_id=tenant.id, roles=[], scope="q360.read q360.audit")
    assert reader.post("/api/v1/quotes/renewals", {"sourcePolicyId": policy["id"]}, format="json").status_code == 403
