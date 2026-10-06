from decimal import Decimal

from apps.business_config.seed.actuarial_model import build_actuarial_model
from apps.business_config.application.pricing import (
    resolve_actuarial_coverage_premiums,
    resolve_actuarial_group_adjustment,
)


def test_actuarial_model_imports_reference_assumptions_as_unapproved_draft():
    model = build_actuarial_model()

    assert model["model_status"] == "DRAFT_REQUIRES_ACTUARIAL_APPROVAL"
    assert model["currency_code"] == "AOA"
    assert model["assumptions"]["usd_to_aoa"] == 931.27
    assert model["assumptions"]["loadings"]["SAU"]["administration_expense"] == 0.13
    assert model["assumptions"]["loadings"]["SAG"]["arseg_levy"] == 0.01
    assert len(model["coverage_assumptions"]) == 17
    assert len(model["age_gender_relativities"]) == 17
    assert len(model["plan_coverages"]["SAU"]) == 51
    assert len(model["plan_coverages"]["SAG"]) == 51
    assert len(model["reference_pure_premiums"]) == 94
    first_rate = model["reference_pure_premiums"][0]
    assert first_rate["segment"] == "SAU"
    assert first_rate["plan"] == "Base"
    assert first_rate["coverage_code"] == "HOSP_INT"
    assert first_rate["capital_sublimit_aoa"] == 5000000
    assert first_rate["annual_pure_premium"] == "33153.5534214757"
    assert first_rate["source_cell"] == "Matriz_SAU!S6"
    assert model["group_size_factors"][0]["premium_adjustment"] == 0.15
    assert model["adjustment_assumptions"]["maximum_cumulative_discount"] == -0.2


def test_actuarial_pricing_reconciles_excel_reference_and_recalculates_lev():
    model = build_actuarial_model()
    coverage = [{"code": "HOSPITALIZATION", "contracted": True}]

    reference = resolve_actuarial_coverage_premiums(
        model=model, plan_code="IND-BASE", coverages=coverage, age=30, sex_code="M"
    )[0]
    excel_reference = next(row for row in model["reference_pure_premiums"] if row["source_cell"] == "Matriz_SAU!S6")
    assert reference["pure_premium"].quantize(Decimal("0.01")) == Decimal(
        excel_reference["annual_pure_premium"]
    ).quantize(Decimal("0.01"))
    assert reference["age_band"] == "18-35"
    assert reference["sex"] == "M"

    model["plan_coverages"]["SAU"][0]["capital_sublimit_aoa"] = 1_000_000
    lower_capital = resolve_actuarial_coverage_premiums(
        model=model, plan_code="IND-BASE", coverages=coverage, age=30, sex_code="M"
    )[0]
    assert lower_capital["pure_premium"] < reference["pure_premium"]


def test_group_actuarial_adjustment_uses_size_adhesion_industry_and_region():
    model = {
        "plan_code_mapping": {"GRP-QUADROS": {"segment": "SAG", "actuarial_plan": "Quadros Médios"}},
        "assumptions": {"loadings": {"SAG": {"volatility": "0.05"}}},
        "group_size_factors": [{
            "headcount_from": 11, "headcount_to": 50,
            "premium_adjustment": 0.05, "volatility": 0.075,
        }],
        "group_participation_factors": [
            {"rule": "Obrigatória — escala", "premium_adjustment": -0.05},
            {"rule": "Obrigatória — preexistências", "premium_adjustment": 0.03},
            {"rule": "Facultativa < 50%", "minimum_participation": 0, "premium_adjustment": 0.3},
            {"rule": "Facultativa 50%–74%", "minimum_participation": 0.5, "premium_adjustment": 0.18},
        ],
        "industry_factors": [{"industry": "Petróleo e Gás", "factor": 1.15}],
        "adjustment_assumptions": {"regional_factors": [{"region": "Luanda (Grande Luanda)", "factor": 1}]},
    }

    result = resolve_actuarial_group_adjustment(
        model=model,
        plan_code="GRP-QUADROS",
        headcount=40,
        profile={"adhesion": "MANDATORY", "industry": "Petróleo e Gás", "region": "Luanda (Grande Luanda)"},
    )

    assert result["volatility"] == Decimal("0.075")
    assert result["factor"] == Decimal("1.05") * Decimal("0.95") * Decimal("1.03") * Decimal("1.15")