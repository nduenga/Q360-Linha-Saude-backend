"""Simulador GTE sobre a cotação: escolhas (coberturas opcionais, opção A–E,
"e se..." de capitais), agravamentos e descontos (R3), doenças preexistentes
por pessoa (6 tratamentos do PDF) e pré-visualização sem gravar."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from apps.product.domain.market_templates import PARTICIPATION_OPTIONS
from apps.quote.infrastructure.models import AuthorityPolicy
from tests.quote.conftest import make_client

SETTINGS = {
    "segment": "INDIVIDUAL_FAMILY",
    "tier": "MEDIUM",
    "accessSystem": "MIXED",
    "participationOptions": PARTICIPATION_OPTIONS,
    "participationOption": "B",
}


def _benefit(client, code):
    return next(i for i in client.get(f"/api/v1/benefits?q={code}&status=ALL&size=200").data["items"] if i["code"] == code)


def _scope(client, *, members=2, settings=SETTINGS):
    product = client.post("/api/v1/products", {"code": "SIM-PROD", "name": "SIM"}).data
    plan = client.post(
        "/api/v1/plans",
        {"productId": product["id"], "code": "SIM-PLAN", "name": "SIM", "settings": settings,
         "complementaryBenefitIds": [_benefit(client, "DENTAL")["id"]]},
        format="json",
    ).data
    client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{_benefit(client, 'HOSPITALIZATION')['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "15000000"}]}},
        format="json",
    )
    client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{_benefit(client, 'DENTAL')['id']}",
        {"configuration": {"inclusion": "OPTIONAL", "limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "250000"}]}},
        format="json",
    )
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "SIM-PARAMS", "effectiveFrom": "2026-01-01",
         "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "100.00"},
                        {"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "10"}]},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")
    table = client.post(
        "/api/v1/rating-tables",
        {"code": "SIM-TABLE", "name": "SIM", "effectiveFrom": "2026-01-01", "currencyCode": "AOA",
         "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}]},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rating-table/{table['id']}/publish")
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": "SIM-ELIG", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    
    proposer_response = client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": "123456789LA042",
            "dateOfBirth": "1990-01-01",
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
        format="json",
    )
    assert proposer_response.status_code in (200, 201), proposer_response.data
    proposer = proposer_response.data["id"]

    quote = client.post(
        "/api/v1/quotes", {"proposerId": proposer, "planId": plan["id"]}, format="json"
    ).data
    
    member_ids = []
    for index in range(members):
        relationship_code = "TITULAR" if index == 0 else "CONJUGE"

        member_response = client.post(
            "/api/v1/members",
            {
                "proposerId": proposer,
                "relationshipCode": relationship_code,
                "dateOfBirth": "1990-01-01",
            },
            format="json",
        )
        assert member_response.status_code in (200, 201), member_response.data
        member_id = member_response.data["id"]
        attach_response = client.post(
            f"/api/v1/quotes/{quote['id']}/members",
            {"memberId": member_id},
            format="json",
        )
        assert attach_response.status_code in (200, 201), attach_response.data
        member_ids.append(member_id)

    priced = client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert priced.status_code == 200, priced.data
    return {"quoteId": quote["id"], "memberIds": member_ids, "planId": plan["id"], "proposerId": proposer}


def _quote(client, scope):
    return client.get(f"/api/v1/quotes/{scope['quoteId']}").data


def _total(client, scope) -> Decimal:
    quote = _quote(client, scope)
    return Decimal(client.get(f"/api/v1/pricing/runs/{quote['latestPricingRunId']}").data["totalAmount"])


def _runs(client) -> int:
    return client.get("/api/v1/pricing/runs").data["page"]["totalElements"]


# ------------------------------------------------------------------- selection
@pytest.mark.django_db
def test_selection_changes_the_premium_and_reprices(admin_client):
    scope = _scope(admin_client)
    quote = _quote(admin_client, scope)
    assert quote["status"] == "READY" and quote["selection"] == {}
    assert _total(admin_client, scope) == Decimal("200.00")

    updated = admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/selection",
        {"selection": {"participationOption": "C", "optionalBenefitCodes": ["DENTAL"]}, "rowVersion": quote["rowVersion"]},
        format="json",
    )
    assert updated.status_code == 200, updated.data
    assert updated.data["status"] == "READY"  # re-priced automatically
    assert updated.data["selection"] == {"optionalBenefitCodes": ["DENTAL"], "participationOption": "C"}
    # (100 * 0.93) + 10 de cobertura dentária (10% do prémio base) = 103.00 por pessoa
    assert _total(admin_client, scope) == Decimal("206.00")
    assert admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/selection").data["selection"]["participationOption"] == "C"


@pytest.mark.django_db
def test_selection_validation_and_optimistic_locking(admin_client):
    scope = _scope(admin_client)
    quote = _quote(admin_client, scope)
    url = f"/api/v1/quotes/{scope['quoteId']}/selection"
    for bad in ({"participationOption": "Z"}, {"optionalBenefitCodes": ["OPTICAL"]}, {"coverageOverrides": {"NOPE": {}}}):
        assert admin_client.put(url, {"selection": bad, "rowVersion": quote["rowVersion"]}, format="json").status_code == 400
    ok = admin_client.put(url, {"selection": {"participationOption": "D"}, "rowVersion": quote["rowVersion"]}, format="json")
    assert ok.status_code == 200
    stale = admin_client.put(url, {"selection": {"participationOption": "A"}, "rowVersion": quote["rowVersion"]}, format="json")
    assert stale.status_code == 409 and stale.data["code"] == "VERSION-CONFLICT"


@pytest.mark.django_db
def test_what_if_capital_override_is_validated_like_a_real_edit(admin_client):
    scope = _scope(admin_client)
    quote = _quote(admin_client, scope)
    url = f"/api/v1/quotes/{scope['quoteId']}/selection"
    bad = {"coverageOverrides": {"HOSPITALIZATION": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "100"}, {"kind": "SUBLIMIT", "label": "x", "amount": "900"}]}}}
    assert admin_client.put(url, {"selection": bad, "rowVersion": quote["rowVersion"]}, format="json").status_code == 400
    good = {"coverageOverrides": {"HOSPITALIZATION": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "40000000"}]}}}
    resp = admin_client.put(url, {"selection": good, "rowVersion": quote["rowVersion"]}, format="json")
    assert resp.status_code == 200
    # a "e se" nunca toca no plano real
    plan_rows = {r["benefit"]["code"]: r["configurationJson"] for r in admin_client.get(f"/api/v1/plans/{scope['planId']}/benefits").data}
    assert plan_rows["HOSPITALIZATION"]["limits"][0]["amount"] == "15000000"


@pytest.mark.django_db
def test_selection_is_frozen_in_the_pricing_snapshot(admin_client):
    scope = _scope(admin_client)
    quote = _quote(admin_client, scope)
    admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/selection",
        {"selection": {"participationOption": "A"}, "rowVersion": quote["rowVersion"]},
        format="json",
    )
    run = _quote(admin_client, scope)["latestPricingRunId"]
    steps = admin_client.get(f"/api/v1/pricing/{run}/explanation").data["steps"]
    assert any(step["stepCode"] == "PARTICIPATION_OPTION_APPLIED" and step["ruleCode"] == "A" for step in steps)


# --------------------------------------------------------------------- preview
@pytest.mark.django_db
def test_preview_shows_the_delta_without_saving_anything(admin_client):
    scope = _scope(admin_client)
    runs_before = _runs(admin_client)
    before = _quote(admin_client, scope)

    preview = admin_client.post(
        f"/api/v1/quotes/{scope['quoteId']}/preview",
        {"selection": {"participationOption": "A"}, "adjustments": [{"kind": "DISCOUNT_PERCENT", "value": "5"}]},
        format="json",
    )
    assert preview.status_code == 200, preview.data
    assert preview.data["preview"] is True and preview.data["pricingRunId"] is None
    # A (+15%) e depois -5%: 100 * 1.15 * 0.95 = 109.25 por pessoa
    assert preview.data["totalAmount"] == "218.50"
    assert preview.data["baseline"]["totalAmount"] == "200.00"
    assert preview.data["impact"] == {
        "previousTotal": "200.00", "newTotal": "218.50", "delta": "18.50", "deltaPercent": "9.25", "currencyCode": "AOA",
    }
    assert _runs(admin_client) == runs_before
    assert _quote(admin_client, scope) == before  # a cotação não mudou


@pytest.mark.django_db
def test_preview_without_overrides_equals_the_saved_state(admin_client):
    scope = _scope(admin_client)
    preview = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/preview", {}, format="json").data
    assert preview["totalAmount"] == "200.00" and preview["impact"]["delta"] == "0.00"


# ----------------------------------------------------------------- adjustments
@pytest.mark.django_db
def test_dry_run_adjustment_simulates_without_saving(admin_client):
    scope = _scope(admin_client)
    runs_before = _runs(admin_client)
    result = admin_client.post(
        f"/api/v1/quotes/{scope['quoteId']}/adjustments?dryRun=true",
        {"kind": "SURCHARGE_PERCENT", "value": "10"},
        format="json",
    )
    assert result.status_code == 200, result.data
    assert result.data == {
        "dryRun": True, "requiresApproval": False, "previousTotal": "200.00", "newTotal": "220.00",
        "delta": "20.00", "deltaPercent": "10.00", "currencyCode": "AOA",
    }
    assert admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/adjustments").data == []
    assert _runs(admin_client) == runs_before
    assert _total(admin_client, scope) == Decimal("200.00")


@pytest.mark.django_db
def test_apply_surcharge_requires_reason_reprices_and_records_impact(admin_client):
    scope = _scope(admin_client)
    url = f"/api/v1/quotes/{scope['quoteId']}/adjustments"
    no_reason = admin_client.post(url, {"kind": "SURCHARGE_PERCENT", "value": "10", "reason": "curto"}, format="json")
    assert no_reason.status_code == 400

    applied = admin_client.post(
        url, {"kind": "SURCHARGE_PERCENT", "value": "10", "reason": "Sinistralidade elevada no grupo"}, format="json"
    )
    assert applied.status_code == 201, applied.data
    assert applied.data["quote"]["status"] == "READY"
    assert applied.data["impact"] == {
        "previousTotal": "200.00", "newTotal": "220.00", "delta": "20.00", "deltaPercent": "10.00",
        "currencyCode": "AOA", "aboveAuthorityLimit": False,
    }
    assert _total(admin_client, scope) == Decimal("220.00")

    run_id = _quote(admin_client, scope)["latestPricingRunId"]
    steps = admin_client.get(f"/api/v1/pricing/{run_id}/explanation").data["steps"]
    assert any(
        step["stepCode"] == "COMMERCIAL_ADJUSTMENT_APPLIED" and step["ruleCode"].startswith("ADJ_SURCHARGE_PERCENT_")
        for step in steps
    )

    listed = admin_client.get(url).data
    assert len(listed) == 1 and listed[0]["status"] == "ACTIVE" and listed[0]["value"] == "10"
    assert listed[0]["reason"] == "Sinistralidade elevada no grupo"


@pytest.mark.django_db
def test_all_adjustment_kinds_and_scopes(admin_client):
    scope = _scope(admin_client)
    first, second = scope["memberIds"]
    url = f"/api/v1/quotes/{scope['quoteId']}/adjustments"

    def simulate(**body):
        return admin_client.post(f"{url}?dryRun=true", body, format="json").data["newTotal"]

    assert simulate(kind="DISCOUNT_PERCENT", value="10") == "180.00"
    assert simulate(kind="SURCHARGE_AMOUNT", value="50", scope="QUOTE") == "250.00"  # uma vez, no total
    assert simulate(kind="DISCOUNT_AMOUNT", value="30", scope="QUOTE") == "170.00"
    assert simulate(kind="SURCHARGE_AMOUNT", value="25", scope="MEMBER", memberId=first) == "225.00"
    assert simulate(kind="DISCOUNT_PERCENT", value="50", scope="MEMBER", memberId=second) == "150.00"


@pytest.mark.django_db
def test_stacked_adjustments_apply_in_order_and_removal_restores_the_price(admin_client):
    scope = _scope(admin_client)
    url = f"/api/v1/quotes/{scope['quoteId']}/adjustments"
    a = admin_client.post(url, {"kind": "SURCHARGE_PERCENT", "value": "10", "reason": "Agravamento por sinistralidade"}, format="json").data
    b = admin_client.post(url, {"kind": "DISCOUNT_PERCENT", "value": "5", "reason": "Desconto comercial de fidelização"}, format="json").data
    # 100 * 1.10 * 0.95 = 104.50 por pessoa
    assert _total(admin_client, scope) == Decimal("209.00")

    short = admin_client.delete(f"{url}/{a['adjustment']['id']}", {"reason": "x"}, format="json")
    assert short.status_code == 400
    removed = admin_client.delete(f"{url}/{a['adjustment']['id']}", {"reason": "Agravamento revisto pelo GTE"}, format="json")
    assert removed.status_code == 200
    assert removed.data["adjustment"]["status"] == "REMOVED" and removed.data["adjustment"]["removedReason"] == "Agravamento revisto pelo GTE"
    assert _total(admin_client, scope) == Decimal("190.00")  # só o desconto de 5%

    # nunca se apaga: continua na lista como REMOVED
    all_rows = admin_client.get(url).data
    assert [r["status"] for r in all_rows] == ["REMOVED", "ACTIVE"]
    assert len(admin_client.get(f"{url}?status=ACTIVE").data) == 1
    again = admin_client.delete(f"{url}/{a['adjustment']['id']}", {"reason": "Tentativa repetida inválida"}, format="json")
    assert again.status_code == 409
    assert admin_client.delete(f"{url}/{b['adjustment']['id']}", {"reason": "Remover o desconto também"}, format="json").status_code == 200
    assert _total(admin_client, scope) == Decimal("200.00")


@pytest.mark.django_db
def test_invalid_adjustments_are_rejected(admin_client):
    scope = _scope(admin_client)
    url = f"/api/v1/quotes/{scope['quoteId']}/adjustments"
    import uuid

    cases = [
        {"kind": "SURCHARGE_PERCENT", "value": "0"},
        {"kind": "SURCHARGE_PERCENT", "value": "-5"},
        {"kind": "SURCHARGE_PERCENT", "value": "abc"},
        {"kind": "DISCOUNT_PERCENT", "value": "100"},
        {"kind": "WHATEVER", "value": "5"},
        {"kind": "SURCHARGE_AMOUNT", "value": "5", "scope": "MEMBER"},
        {"kind": "SURCHARGE_AMOUNT", "value": "5", "scope": "MEMBER", "memberId": str(uuid.uuid4())},
        {"kind": "SURCHARGE_AMOUNT", "value": "5", "scope": "QUOTE", "memberId": scope["memberIds"][0]},
    ]
    for body in cases:
        resp = admin_client.post(f"{url}?dryRun=true", body, format="json")
        assert resp.status_code == 400, body
        assert admin_client.post(url, {**body, "reason": "Justificação suficiente"}, format="json").status_code == 400, body
    # um desconto fixo maior que o prémio falha o cálculo e não grava nada
    huge = admin_client.post(url, {"kind": "DISCOUNT_AMOUNT", "value": "500", "scope": "QUOTE", "reason": "Desconto exagerado de teste"}, format="json")
    assert huge.status_code == 422
    assert admin_client.get(url).data == []
    assert _total(admin_client, scope) == Decimal("200.00")


@pytest.mark.django_db
def test_adjustments_only_while_quote_is_draft_or_ready(admin_client):
    scope = _scope(admin_client)
    quote = _quote(admin_client, scope)
    admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/cancel", {"reasonCode": "TEST", "reasonText": "teste", "rowVersion": quote["rowVersion"]}, format="json")
    resp = admin_client.post(
        f"/api/v1/quotes/{scope['quoteId']}/adjustments", {"kind": "SURCHARGE_PERCENT", "value": "5", "reason": "Cotação já cancelada"}, format="json"
    )
    assert resp.status_code == 409 and resp.data["code"] == "QUOTE-STATE"


@pytest.mark.django_db
def test_authority_limit_requires_an_approver_above_the_threshold(admin_client, tenant):
    scope = _scope(admin_client)
    AuthorityPolicy._base_manager.create(
        tenant_id=tenant.id, code="AUTH", version_no=1, effective_from="2026-01-01", status="PUBLISHED",
        policy_json={"maxAdjustmentPct": "5", "maxAdjustmentAmount": "100"},
    )
    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write", actor_id="sub-1")
    url = f"/api/v1/quotes/{scope['quoteId']}/adjustments"

    within = subscriber.post(url, {"kind": "SURCHARGE_PERCENT", "value": "4", "reason": "Dentro do limite permitido"}, format="json")
    assert within.status_code == 201 and within.data["impact"]["aboveAuthorityLimit"] is False

    over = subscriber.post(url, {"kind": "SURCHARGE_PERCENT", "value": "10", "reason": "Acima do limite permitido"}, format="json")
    assert over.status_code == 403 and over.data["code"] == "SEC-403"
    over_amount = subscriber.post(url, {"kind": "DISCOUNT_AMOUNT", "value": "120", "scope": "QUOTE", "reason": "Desconto fixo acima do limite"}, format="json")
    assert over_amount.status_code == 403

    dry = subscriber.post(f"{url}?dryRun=true", {"kind": "SURCHARGE_PERCENT", "value": "10"}, format="json")
    assert dry.status_code == 200 and dry.data["requiresApproval"] is True

    approver = admin_client.post(url, {"kind": "SURCHARGE_PERCENT", "value": "10", "reason": "Aprovado pelo responsável"}, format="json")
    assert approver.status_code == 201 and approver.data["impact"]["aboveAuthorityLimit"] is True


@pytest.mark.django_db
def test_adjustment_changes_are_audited_with_before_after_reason_and_impact(admin_client, tenant):
    scope = _scope(admin_client)
    url = f"/api/v1/quotes/{scope['quoteId']}/adjustments"
    applied = admin_client.post(url, {"kind": "SURCHARGE_PERCENT", "value": "10", "reason": "Motivo auditável do ajuste"}, format="json").data
    admin_client.delete(f"{url}/{applied['adjustment']['id']}", {"reason": "Motivo auditável da remoção"}, format="json")
    auditor = make_client(tenant_id=tenant.id, roles=[], scope="q360.read q360.audit")
    events = auditor.get(f"/api/v1/audit-events?entityId={scope['quoteId']}&size=200").data["items"]
    by_action = {e["action"]: e["metadata"] for e in events}
    assert by_action["quote.adjustment_applied"]["reason"] == "Motivo auditável do ajuste"
    assert by_action["quote.adjustment_applied"]["impact"]["delta"] == "20.00"
    assert by_action["quote.adjustment_removed"]["reason"] == "Motivo auditável da remoção"
    assert by_action["quote.adjustment_removed"]["before"]["kind"] == "SURCHARGE_PERCENT"


# --------------------------------------------------- doenças preexistentes
@pytest.mark.django_db
def test_pre_existing_loading_changes_one_members_premium(admin_client):
    scope = _scope(admin_client)
    first = scope["memberIds"][0]
    url = f"/api/v1/quotes/{scope['quoteId']}/members/{first}/pre-existing"
    resp = admin_client.put(
        url,
        {"decision": {"mode": "ACCEPTED_WITH_LOADING", "loadingPct": "25", "condition": "Hipertensão", "clinicalQuestionnaireCompleted": True},
         "reason": "Aceite após análise do questionário clínico"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["preExisting"]["mode"] == "ACCEPTED_WITH_LOADING"
    assert resp.data["preExisting"]["decidedBy"]
    # 100 * 1.25 + 100 = 225.00
    assert _total(admin_client, scope) == Decimal("225.00")
    members = {m["memberId"]: m for m in admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/members").data["items"]}
    assert members[first]["preExisting"]["loadingPct"] == "25"

    cleared = admin_client.delete(url, {"reason": "Decisão revista pelo médico"}, format="json")
    assert cleared.status_code == 200
    assert _total(admin_client, scope) == Decimal("200.00")


@pytest.mark.django_db
def test_pre_existing_decision_rules_per_the_pdf(admin_client):
    scope = _scope(admin_client)
    url = f"/api/v1/quotes/{scope['quoteId']}/members/{scope['memberIds'][0]}/pre-existing"
    reason = "Decisão de subscrição de teste"

    def put(decision, expected):
        resp = admin_client.put(url, {"decision": decision, "reason": reason}, format="json")
        assert resp.status_code == expected, (decision, resp.data)
        return resp

    put({"mode": "TOTAL_EXCLUSION"}, 200)
    put({"mode": "SPECIFIC_EXCLUSION", "condition": "Diabetes", "clinicalQuestionnaireCompleted": True}, 200)
    put({"mode": "SPECIFIC_EXCLUSION", "clinicalQuestionnaireCompleted": True}, 400)  # falta a doença declarada
    put({"mode": "ACCEPTED_WITH_SUBLIMIT", "sublimitAmount": "500000", "clinicalQuestionnaireCompleted": True}, 200)
    put({"mode": "ACCEPTED_WITH_SUBLIMIT", "clinicalQuestionnaireCompleted": True}, 400)
    put({"mode": "ACCEPTED_WITH_LOADING", "loadingPct": "20"}, 400)  # sem questionário clínico
    put({"mode": "ACCEPTED_WITH_LOADING", "clinicalQuestionnaireCompleted": True}, 400)
    put({"mode": "ACCEPTED_WITH_WAITING", "waitingMonths": 18, "clinicalQuestionnaireCompleted": True}, 200)
    for months in (6, 11, 25):
        put({"mode": "ACCEPTED_WITH_WAITING", "waitingMonths": months, "clinicalQuestionnaireCompleted": True}, 400)
    put({"mode": "FULL_ACCEPTANCE", "clinicalQuestionnaireCompleted": True}, 400)  # só grupo com adesão obrigatória
    put({"mode": "MAGIC"}, 400)
    short = admin_client.put(url, {"decision": {"mode": "TOTAL_EXCLUSION"}, "reason": "curto"}, format="json")
    assert short.status_code == 400


@pytest.mark.django_db
def test_group_pre_existing_full_acceptance_and_sublimit(admin_client):
    group = {"segment": "GROUP", "tier": "CUSTOM", "category": "Quadros", "accessSystem": "MIXED",
             "group": {"minInsured": 5, "adhesion": "MANDATORY"}}
    scope = _scope(admin_client, settings=group)
    url = f"/api/v1/quotes/{scope['quoteId']}/members/{scope['memberIds'][0]}/pre-existing"
    reason = "Grupo com adesão obrigatória"
    assert admin_client.put(url, {"decision": {"mode": "FULL_ACCEPTANCE"}, "reason": reason}, format="json").status_code == 200
    assert admin_client.put(url, {"decision": {"mode": "ACCEPTED_WITH_SUBLIMIT", "sublimitAmount": "1000000"}, "reason": reason}, format="json").status_code == 200
    # tratamentos próprios do individual não existem no grupo
    for mode in ("ACCEPTED_WITH_LOADING", "ACCEPTED_WITH_WAITING", "SPECIFIC_EXCLUSION", "TOTAL_EXCLUSION"):
        resp = admin_client.put(url, {"decision": {"mode": mode, "loadingPct": "10", "waitingMonths": 12, "condition": "x"}, "reason": reason}, format="json")
        assert resp.status_code == 400, mode


@pytest.mark.django_db
def test_pre_existing_requires_the_member_to_be_on_the_quote(admin_client):
    import uuid

    scope = _scope(admin_client)
    resp = admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/members/{uuid.uuid4()}/pre-existing",
        {"decision": {"mode": "TOTAL_EXCLUSION"}, "reason": "Membro inexistente na cotação"},
        format="json",
    )
    assert resp.status_code == 400
