"""Q360-S4-02/S4-04/S5-01/S5-02 acceptance criteria: "Mesma entrada produz
mesmo resultado • Sem floating point • Breakdown disponível" (S4-02),
"Cada componente tem origem/versão" (S4-04), "Não altera quote oficial"
(S5-02)."""
from __future__ import annotations

import json

import pytest


def _plan(client, *, product_code: str) -> dict:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    plan = client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"}).data
    return {"productId": product["id"], "planId": plan["id"]}


def _parameter_set(client, *, code: str, base_premium: str = "100.00") -> str:
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": code,
            "effectiveFrom": "2026-01-01",
            "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": base_premium}],
        },
        format="json",
    ).data
    client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")
    return code


def _rating_table(client, *, code: str) -> str:
    created = client.post(
        "/api/v1/rating-tables",
        {
            "code": code,
            "name": code,
            "effectiveFrom": "2026-01-01",
            "currencyCode": "AOA",
            "factors": [
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "30-39"}, "factorValue": "1.00"},
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "70+"}, "factorValue": "2.00"},
                {"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00", "priority": -1},
            ],
        },
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")
    return code


def _member(client) -> str:
    proposer = client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": "123456789LA042",
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data
    member = client.post(
        "/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR"}
    ).data
    return member["id"]


def _calc_body(*, plan_ref: dict, param_code: str, table_code: str, member_id: str, age_band: str = "30-39") -> dict:
    return {
        "planId": plan_ref["planId"],
        "effectiveDate": "2026-06-01",
        "memberIds": [member_id],
        "context": {
            "ratingTableCode": table_code,
            "parameterSetCode": param_code,
            "members": {member_id: {"ageBand": age_band}},
        },
    }


@pytest.mark.django_db
def test_calculate_pricing_happy_path(admin_client):
    plan_ref = _plan(admin_client, product_code="PRICE-1")
    param_code = _parameter_set(admin_client, code="PARAMS-1", base_premium="100.00")
    table_code = _rating_table(admin_client, code="TABLE-1")
    member_id = _member(admin_client)

    response = admin_client.post(
        "/api/v1/pricing/calculate",
        _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id, age_band="70+"),
        format="json",
    )
    assert response.status_code == 200, response.data
    body = response.data
    assert body["status"] == "CALCULATED"
    assert body["currencyCode"] == "AOA"
    # 100.00 base * 2.00 age factor (70+) = 200.00
    assert body["totalAmount"] == "200.00"
    codes = [c["code"] for c in body["components"]]
    assert codes == ["BASE_PREMIUM", "AGE_FACTOR", "TOTAL"]
    assert body["versions"]["roundingPolicyCode"]
    assert body["versions"]["ruleVersionId"] is None


@pytest.mark.django_db
def test_calculate_pricing_with_idempotency_enabled(admin_client, settings):
    """Regression: `versions` used to hold raw UUIDs, which the idempotency
    middleware could not persist to its JSONField -> HTTP 500 in any
    environment with IDEMPOTENCY_REQUIRED=True (the testing settings turn
    it off, which is why the happy-path test above never caught it)."""
    plan_ref = _plan(admin_client, product_code="PRICE-IDEMP")
    param_code = _parameter_set(admin_client, code="PARAMS-IDEMP")
    table_code = _rating_table(admin_client, code="TABLE-IDEMP")
    member_id = _member(admin_client)
    settings.IDEMPOTENCY_REQUIRED = True

    body = _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id)
    first = admin_client.post(
        "/api/v1/pricing/calculate", body, format="json", HTTP_IDEMPOTENCY_KEY="pricing-idemp-1"
    )
    assert first.status_code == 200
    assert first.data["versions"]["productId"] == plan_ref["productId"]

    replay = admin_client.post(
        "/api/v1/pricing/calculate", body, format="json", HTTP_IDEMPOTENCY_KEY="pricing-idemp-1"
    )
    assert replay.status_code == 200
    assert replay.json()["pricingRunId"] == str(first.data["pricingRunId"])


@pytest.mark.django_db
def test_same_input_produces_same_result(admin_client):
    plan_ref = _plan(admin_client, product_code="PRICE-2")
    param_code = _parameter_set(admin_client, code="PARAMS-2")
    table_code = _rating_table(admin_client, code="TABLE-2")
    member_id = _member(admin_client)
    body = _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id)

    first = admin_client.post("/api/v1/pricing/calculate", body, format="json").data
    second = admin_client.post("/api/v1/pricing/calculate", body, format="json").data
    assert first["totalAmount"] == second["totalAmount"] == "100.00"
    assert first["pricingRunId"] != second["pricingRunId"]


@pytest.mark.django_db
def test_missing_context_keys_rejected(admin_client):
    plan_ref = _plan(admin_client, product_code="PRICE-3")
    member_id = _member(admin_client)
    response = admin_client.post(
        "/api/v1/pricing/calculate",
        {
            "planId": plan_ref["planId"],
            "effectiveDate": "2026-06-01",
            "memberIds": [member_id],
            "context": {},
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_unresolvable_rating_table_is_pricing_config_error(admin_client):
    plan_ref = _plan(admin_client, product_code="PRICE-4")
    param_code = _parameter_set(admin_client, code="PARAMS-4")
    member_id = _member(admin_client)
    response = admin_client.post(
        "/api/v1/pricing/calculate",
        _calc_body(plan_ref=plan_ref, param_code=param_code, table_code="NO-SUCH-TABLE", member_id=member_id),
        format="json",
    )
    assert response.status_code == 422
    assert response.data["code"] == "PRICING-CONFIG"


@pytest.mark.django_db
def test_explanation_endpoint_returns_ordered_steps(admin_client):
    plan_ref = _plan(admin_client, product_code="PRICE-5")
    param_code = _parameter_set(admin_client, code="PARAMS-5")
    table_code = _rating_table(admin_client, code="TABLE-5")
    member_id = _member(admin_client)
    run = admin_client.post(
        "/api/v1/pricing/calculate",
        _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id),
        format="json",
    ).data

    response = admin_client.get(f"/api/v1/pricing/{run['pricingRunId']}/explanation")
    assert response.status_code == 200
    body = response.data
    assert body["pricingRunId"] == run["pricingRunId"]
    sequences = [s["sequence"] for s in body["steps"]]
    assert sequences == sorted(sequences)
    assert any(s["stepCode"] == "TOTAL_COMPUTED" for s in body["steps"])


@pytest.mark.django_db
def test_explanation_unknown_run_is_not_found(admin_client):
    import uuid

    response = admin_client.get(f"/api/v1/pricing/{uuid.uuid4()}/explanation")
    assert response.status_code == 404
    assert response.data["code"] == "NOT-FOUND"


@pytest.mark.django_db
def test_scenario_does_not_alter_base_run(admin_client):
    plan_ref = _plan(admin_client, product_code="PRICE-6")
    param_code = _parameter_set(admin_client, code="PARAMS-6")
    table_code = _rating_table(admin_client, code="TABLE-6")
    member_id = _member(admin_client)
    base_run = admin_client.post(
        "/api/v1/pricing/calculate",
        _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id, age_band="30-39"),
        format="json",
    ).data
    assert base_run["totalAmount"] == "100.00"

    scenario_response = admin_client.post(
        "/api/v1/pricing/scenarios",
        {
            "basePricingRunId": base_run["pricingRunId"],
            "name": "What if 70+",
            "overrides": {"context": {"members": {member_id: {"ageBand": "70+"}}}},
        },
        format="json",
    )
    assert scenario_response.status_code == 201
    scenario_body = scenario_response.data
    assert scenario_body["totalAmount"] == "200.00"
    assert scenario_body["pricingRunId"] != base_run["pricingRunId"]

    # Base run untouched.
    unchanged = admin_client.get(f"/api/v1/pricing/{base_run['pricingRunId']}/explanation")
    assert unchanged.status_code == 200


@pytest.mark.django_db
def test_scenario_unknown_base_run_is_not_found(admin_client):
    import uuid

    response = admin_client.post(
        "/api/v1/pricing/scenarios",
        {"basePricingRunId": str(uuid.uuid4()), "name": "X", "overrides": {}},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["code"] == "NOT-FOUND"


@pytest.mark.django_db
def test_pricing_rule_version_adjustment_is_applied(admin_client):
    """Q360-S5-01: an optional published PRICING RuleVersion contributes an
    additive ADJUSTMENT component when its `when` matches the member's
    calculation context (see apps.pricing.domain.pricing_rules)."""
    plan_ref = _plan(admin_client, product_code="PRICE-7")
    param_code = _parameter_set(admin_client, code="PARAMS-7")
    table_code = _rating_table(admin_client, code="TABLE-7")
    member_id = _member(admin_client)

    rule_artifact = json.dumps({"adjustments": [{"code": "LOYALTY_DISCOUNT", "when": {"ageBand": "30-39"}, "amount": "-10.00"}]})
    rule_version = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": "PRICING-RULES-7",
            "name": "Pricing rules 7",
            "ruleDomain": "PRICING",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": rule_artifact,
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule_version['id']}/publish")

    body = _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id, age_band="30-39")
    body["context"]["ruleVersionCode"] = "PRICING-RULES-7"

    response = admin_client.post("/api/v1/pricing/calculate", body, format="json")
    assert response.status_code == 200
    result = response.data
    assert result["totalAmount"] == "90.00"
    assert str(result["versions"]["ruleVersionId"]) == rule_version["id"]
    codes = [c["code"] for c in result["components"]]
    assert "LOYALTY_DISCOUNT" in codes


@pytest.mark.django_db
def test_negative_result_fails_the_run(admin_client):
    """Q360-S5-03: an adjustment that would drive a component negative
    fails the run (PRICING-FAILED) rather than persisting a bad price."""
    plan_ref = _plan(admin_client, product_code="PRICE-8")
    param_code = _parameter_set(admin_client, code="PARAMS-8", base_premium="5.00")
    table_code = _rating_table(admin_client, code="TABLE-8")
    member_id = _member(admin_client)

    rule_artifact = json.dumps({"adjustments": [{"code": "OVERSIZED_DISCOUNT", "when": {}, "amount": "-999.00"}]})
    rule_version = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": "PRICING-RULES-8",
            "name": "Pricing rules 8",
            "ruleDomain": "PRICING",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": rule_artifact,
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule_version['id']}/publish")

    body = _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id)
    body["context"]["ruleVersionCode"] = "PRICING-RULES-8"

    response = admin_client.post("/api/v1/pricing/calculate", body, format="json")
    assert response.status_code == 422
    assert response.data["code"] == "PRICING-FAILED"


@pytest.mark.django_db
def test_overflow_result_fails_the_run(admin_client):
    """Q360-S5-03: a runaway factor chain fails the run instead of
    silently overflowing the numeric(30,8) column."""
    plan_ref = _plan(admin_client, product_code="PRICE-9")
    param_code = _parameter_set(admin_client, code="PARAMS-9", base_premium="100.00")
    table_code = _rating_table(admin_client, code="TABLE-9")
    member_id = _member(admin_client)

    rule_artifact = json.dumps(
        {"adjustments": [{"code": "RUNAWAY", "when": {}, "amount": "999999999999999.00"}]}
    )
    rule_version = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": "PRICING-RULES-9",
            "name": "Pricing rules 9",
            "ruleDomain": "PRICING",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": rule_artifact,
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule_version['id']}/publish")

    body = _calc_body(plan_ref=plan_ref, param_code=param_code, table_code=table_code, member_id=member_id)
    body["context"]["ruleVersionCode"] = "PRICING-RULES-9"

    response = admin_client.post("/api/v1/pricing/calculate", body, format="json")
    assert response.status_code == 422
    assert response.data["code"] == "PRICING-FAILED"
