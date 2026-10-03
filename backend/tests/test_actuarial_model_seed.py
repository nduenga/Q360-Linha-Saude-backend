from apps.business_config.seed.actuarial_model import build_actuarial_model


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
    assert model["group_size_factors"][0]["premium_adjustment"] == 0.15
    assert model["adjustment_assumptions"]["maximum_cumulative_discount"] == -0.2