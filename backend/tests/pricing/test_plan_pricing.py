"""O plano (escalão, capitais), a opção de participação A–E e as coberturas
opcionais escolhidas alteram o prémio — sempre por parâmetros do GTE
(RatingFactor / PricingParameterSet), nunca por valores no código.

PDF "Coberturas e Capitais": "Quanto maior a participação escolhida, menor o
prémio"; as coberturas opcionais ("O") são facultativas e custam à parte.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.product.domain.market_templates import PARTICIPATION_OPTIONS

SETTINGS = {
    "segment": "INDIVIDUAL_FAMILY",
    "tier": "MEDIUM",
    "accessSystem": "MIXED",
    "participationOptions": PARTICIPATION_OPTIONS,
    "participationOption": "B",
}


NO_OPTIONS = {k: v for k, v in SETTINGS.items() if "participation" not in k}


def _benefit(client, code):
    return next(i for i in client.get(f"/api/v1/benefits?q={code}&status=ALL&size=200").data["items"] if i["code"] == code)


def _plan(client, *, code="PP", settings=SETTINGS, product_code=None, hospital_capital="15000000", optional=()):
    product = client.post("/api/v1/products", {"code": product_code or f"PROD-{code}", "name": code}).data
    plan = client.post(
        "/api/v1/plans",
        {"productId": product["id"], "code": code, "name": code, "settings": settings,
         "complementaryBenefitIds": [_benefit(client, c)["id"] for c in optional]},
        format="json",
    ).data
    client.put(
        f"/api/v1/plans/{plan['id']}/benefits/{_benefit(client, 'HOSPITALIZATION')['id']}",
        {"configuration": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": hospital_capital}]}},
        format="json",
    )
    for code_ in optional:
        client.put(
            f"/api/v1/plans/{plan['id']}/benefits/{_benefit(client, code_)['id']}",
            {"configuration": {"inclusion": "OPTIONAL", "limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "250000"}]}},
            format="json",
        )
    return plan["id"]


def _parameter_set(client, *, code="PARAMS", extra=()):
    parameters = [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "100.00"}, *extra]
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": code, "effectiveFrom": "2026-01-01", "parameters": parameters},
        format="json",
    ).data
    assert client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish").status_code in (200, 201, 204)
    return code


def _rating_table(client, *, code="TABLE", factors=()):
    base = [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00", "priority": -1}]
    created = client.post(
        "/api/v1/rating-tables",
        {"code": code, "name": code, "effectiveFrom": "2026-01-01", "currencyCode": "AOA", "factors": [*base, *factors]},
        format="json",
    ).data
    assert client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish").status_code in (200, 201, 204)
    return code


def _member(client):
    proposer = client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "dateOfBirth": "1985-04-12", "displayName": "Holder", "registrationNumber": "123456789LA042",
         "email": "holder@example.com", "phone": "+244900000000"},
    ).data
    return client.post("/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1985-04-12"}).data["id"]


def _body(plan_id, member_id, *, selection=None, table="TABLE", params="PARAMS"):
    context = {"ratingTableCode": table, "parameterSetCode": params, "members": {member_id: {"ageBand": "30-39"}}}
    if selection is not None:
        context["selection"] = selection
    return {"planId": plan_id, "effectiveDate": "2026-06-01", "memberIds": [member_id], "context": context}


def _calc(client, body):
    return client.post("/api/v1/pricing/calculate", body, format="json")


@pytest.mark.django_db
def test_plan_tier_and_capital_dimensions_drive_rating_factors(admin_client):
    """O escalão do plano e o capital de uma cobertura casam com RatingFactor."""
    _parameter_set(admin_client)
    _rating_table(
        admin_client,
        factors=[
            {"factorCode": "TIER_FACTOR", "dimensions": {"tier": "MEDIUM"}, "factorValue": "1.20"},
            {"factorCode": "TIER_FACTOR", "dimensions": {"tier": "SUPERIOR"}, "factorValue": "1.50"},
            {"factorCode": "HOSPITAL_CAPITAL", "dimensions": {"capital.HOSPITALIZATION": "15000000"}, "factorValue": "1.10"},
            {"factorCode": "HOSPITAL_CAPITAL", "dimensions": {"capital.HOSPITALIZATION": "40000000"}, "factorValue": "1.40"},
        ],
    )
    member = _member(admin_client)
    medio = _calc(admin_client, _body(_plan(admin_client, code="MED", settings=NO_OPTIONS), member))
    assert medio.status_code == 200, medio.data
    # 100 * 1.00 (age) * 1.10 (capital 15M) * 1.20 (tier MEDIUM) = 132.00
    assert medio.data["totalAmount"] == "132.00"
    codes = [c["code"] for c in medio.data["components"]]
    assert "TIER_FACTOR" in codes and "HOSPITAL_CAPITAL" in codes

    superior_settings = {**NO_OPTIONS, "tier": "SUPERIOR"}
    superior = _calc(admin_client, _body(_plan(admin_client, code="SUP", settings=superior_settings, hospital_capital="40000000"), member))
    # 100 * 1.40 * 1.50 = 210.00
    assert superior.data["totalAmount"] == "210.00"


@pytest.mark.django_db
def test_higher_participation_option_means_lower_premium(admin_client):
    """PDF: A (sem participação, +15%) > B (standard, 0%) > C (-7%) > D (-12%) > E (só hospitalização, -40%)."""
    _parameter_set(admin_client)
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client)

    totals = {}
    for option in "ABCDE":
        response = _calc(admin_client, _body(plan_id, member, selection={"participationOption": option}))
        assert response.status_code == 200, response.data
        totals[option] = Decimal(response.data["totalAmount"])
        component = next(c for c in response.data["components"] if c["code"] == f"PARTICIPATION_OPTION_{option}")
        assert component["type"] == "FACTOR"
    assert totals == {"A": Decimal("115.00"), "B": Decimal("100.00"), "C": Decimal("93.00"), "D": Decimal("88.00"), "E": Decimal("60.00")}
    assert totals["A"] > totals["B"] > totals["C"] > totals["D"] > totals["E"]


@pytest.mark.django_db
def test_default_participation_option_comes_from_the_plan_settings(admin_client):
    _parameter_set(admin_client)
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client, settings={**SETTINGS, "participationOption": "C"})
    response = _calc(admin_client, _body(plan_id, member))
    assert response.data["totalAmount"] == "93.00"
    explicit = _calc(admin_client, _body(plan_id, member, selection={"participationOption": "A"}))
    assert explicit.data["totalAmount"] == "115.00"


@pytest.mark.django_db
def test_participation_option_can_also_select_the_rating_factor(admin_client):
    """A opção chega também como dimensão, para tabelas do GTE que a usem."""
    _parameter_set(admin_client)
    _rating_table(admin_client, factors=[{"factorCode": "OPTION_TABLE", "dimensions": {"participationOption": "D"}, "factorValue": "1.01"}])
    member = _member(admin_client)
    plan_id = _plan(admin_client)
    response = _calc(admin_client, _body(plan_id, member, selection={"participationOption": "D"}))
    codes = [c["code"] for c in response.data["components"]]
    assert "OPTION_TABLE" in codes


@pytest.mark.django_db
def test_optional_coverage_chosen_adds_its_configured_loading(admin_client):
    """PDF: coberturas opcionais (O) são facultativas; o custo vem do GTE."""
    _parameter_set(admin_client, extra=[{"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "10"}])
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client, optional=("DENTAL",), settings=NO_OPTIONS)

    without = _calc(admin_client, _body(plan_id, member))
    assert without.data["totalAmount"] == "100.00"
    with_dental = _calc(admin_client, _body(plan_id, member, selection={"optionalBenefitCodes": ["DENTAL"]}))
    assert with_dental.status_code == 200
    assert with_dental.data["totalAmount"] == "110.00"
    component = next(c for c in with_dental.data["components"] if c["code"] == "COVERAGE_DENTAL")
    assert component["type"] == "ADJUSTMENT" and component["adjustmentAmount"] == "10.00"
    assert with_dental.data["warnings"] == []


@pytest.mark.django_db
def test_optional_coverage_without_a_loading_parameter_warns_instead_of_failing(admin_client):
    _parameter_set(admin_client)
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client, optional=("DENTAL",), settings=NO_OPTIONS)
    response = _calc(admin_client, _body(plan_id, member, selection={"optionalBenefitCodes": ["DENTAL"]}))
    assert response.status_code == 200
    assert response.data["totalAmount"] == "100.00"
    assert response.data["warnings"][0]["code"] == "COVERAGE_LOADING_DENTAL"
    assert "COVERAGE_LOADING_DENTAL" in response.data["warnings"][0]["message"]


@pytest.mark.django_db
def test_invalid_selection_is_a_400_and_creates_no_pricing_run(admin_client):
    _parameter_set(admin_client)
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client, optional=("DENTAL",))
    for selection in (
        {"optionalBenefitCodes": ["OPTICAL"]},  # não é opcional deste plano
        {"optionalBenefitCodes": ["HOSPITALIZATION"]},  # incluída, não opcional
        {"optionalBenefitCodes": "DENTAL"},
        {"participationOption": "Z"},
    ):
        response = _calc(admin_client, _body(plan_id, member, selection=selection))
        assert response.status_code == 400, selection
    assert admin_client.get("/api/v1/pricing/runs").data["page"]["totalElements"] == 0


@pytest.mark.django_db
def test_preview_matches_calculate_but_persists_nothing(admin_client):
    _parameter_set(admin_client, extra=[{"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "10"}])
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client, optional=("DENTAL",))
    selection = {"optionalBenefitCodes": ["DENTAL"], "participationOption": "C"}

    preview = admin_client.post("/api/v1/pricing/preview", _body(plan_id, member, selection=selection), format="json")
    assert preview.status_code == 200
    assert preview.data["preview"] is True and preview.data["pricingRunId"] is None
    assert admin_client.get("/api/v1/pricing/runs").data["page"]["totalElements"] == 0

    real = _calc(admin_client, _body(plan_id, member, selection=selection))
    assert preview.data["totalAmount"] == real.data["totalAmount"]
    assert [c["code"] for c in preview.data["components"]] == [c["code"] for c in real.data["components"]]
    assert admin_client.get("/api/v1/pricing/runs").data["page"]["totalElements"] == 1


@pytest.mark.django_db
def test_preview_failures_are_reported_and_leave_no_trace(admin_client):
    _parameter_set(admin_client)
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client)
    bad = admin_client.post("/api/v1/pricing/preview", _body(plan_id, member, selection={"participationOption": "Z"}), format="json")
    assert bad.status_code == 400
    missing_config = admin_client.post(
        "/api/v1/pricing/preview", _body(plan_id, member, table="NOPE"), format="json"
    )
    assert missing_config.status_code == 422
    assert admin_client.get("/api/v1/pricing/runs").data["page"]["totalElements"] == 0


@pytest.mark.django_db
def test_same_input_with_selection_is_deterministic(admin_client):
    _parameter_set(admin_client, extra=[{"code": "COVERAGE_LOADING_DENTAL", "valueType": "DECIMAL", "value": "7.5"}])
    _rating_table(admin_client)
    member = _member(admin_client)
    plan_id = _plan(admin_client, optional=("DENTAL",))
    selection = {"optionalBenefitCodes": ["DENTAL"], "participationOption": "D"}
    first = _calc(admin_client, _body(plan_id, member, selection=selection)).data
    second = _calc(admin_client, _body(plan_id, member, selection=selection)).data
    assert first["totalAmount"] == second["totalAmount"]
    assert [(c["code"], c["resultAmount"]) for c in first["components"]] == [(c["code"], c["resultAmount"]) for c in second["components"]]


@pytest.mark.django_db
def test_calculation_without_selection_is_unchanged_for_plans_without_settings(admin_client):
    """Regression: plans created the old way (no settings) price exactly as before."""
    _parameter_set(admin_client)
    _rating_table(admin_client)
    member = _member(admin_client)
    product = admin_client.post("/api/v1/products", {"code": "OLD", "name": "OLD"}).data
    plan = admin_client.post("/api/v1/plans", {"productId": product["id"], "code": "OLDP", "name": "OLDP"}).data
    response = _calc(admin_client, _body(plan["id"], member))
    assert response.status_code == 200
    assert response.data["totalAmount"] == "100.00"
    assert [c["code"] for c in response.data["components"]] == ["BASE_PREMIUM", "AGE_FACTOR", "TOTAL"]
