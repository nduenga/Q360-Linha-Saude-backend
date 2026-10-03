"""Regras do PDF "Seguro de Saúde — Coberturas e Capitais" sobre planos e
capitais, testadas sobre o domínio puro (sem base de dados)."""
from __future__ import annotations

import copy

import pytest

from apps.product.domain.coverage_config import (
    InvalidCoverageConfigError,
    plan_completeness_issues,
    validate_coverage_config,
)
from apps.product.domain.market_catalog import CATALOG_BY_CODE
from apps.product.domain.market_templates import PARTICIPATION_OPTIONS, build_templates
from apps.product.domain.plan_settings import InvalidPlanSettingsError, validate_plan_settings

INDIVIDUAL = {"segment": "INDIVIDUAL_FAMILY", "tier": "MEDIUM", "accessSystem": "MIXED"}
GROUP = {"segment": "GROUP", "tier": "CUSTOM", "accessSystem": "MIXED", "group": {"minInsured": 5, "adhesion": "MANDATORY"}}


def _cfg(code, raw, settings=INDIVIDUAL, category="COMPLEMENTARY"):
    return validate_coverage_config(
        raw,
        benefit_code=code,
        benefit_category=category,
        benefit_definition=CATALOG_BY_CODE[code]["definition"],
        plan_settings=settings,
    )


def _codes(warnings):
    return {w["code"] for w in warnings}


# ------------------------------------------------------------ plan settings
def test_empty_settings_are_allowed():
    assert validate_plan_settings({}) == ({}, [])
    assert validate_plan_settings(None) == ({}, [])


def test_unknown_setting_and_bad_segment_are_rejected():
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({"segment": "GROUP", "bogus": 1})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({"segment": "FAMILY"})


def test_no_pro_rata_rule_cannot_be_disabled():
    """PDF: "No seguro de saúde não há regra de rateio"."""
    normalised, _ = validate_plan_settings({"segment": "GROUP"})
    assert normalised["noProRata"] is True
    with pytest.raises(InvalidPlanSettingsError, match="pro-rata"):
        validate_plan_settings({"segment": "GROUP", "noProRata": False})


def test_individual_age_limits_entry_and_permanence():
    """PDF: idade de entrada até 60–65, renovação até 70–75."""
    ok, warnings = validate_plan_settings({**INDIVIDUAL, "entryAge": {"min": 0, "max": 65}, "permanenceAge": {"max": 75}})
    assert "AGE_LIMITS_MISSING" not in _codes(warnings)
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "entryAge": {"min": 0, "max": 80}, "permanenceAge": {"max": 75}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "entryAge": {"min": 70, "max": 65}})
    _, missing = validate_plan_settings(INDIVIDUAL)
    assert "AGE_LIMITS_MISSING" in _codes(missing)


def test_household_only_on_individual_family():
    validate_plan_settings({**INDIVIDUAL, "household": {"spouse": True, "dependentChildMaxAge": 25}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**GROUP, "household": {"spouse": True}})


def test_clinical_questionnaire_is_mandatory_in_individual():
    with pytest.raises(InvalidPlanSettingsError, match="mandatory"):
        validate_plan_settings({**INDIVIDUAL, "clinicalQuestionnaire": {"required": False}})
    validate_plan_settings({**INDIVIDUAL, "clinicalQuestionnaire": {"required": True, "medicalExamAboveAge": 55}})
    validate_plan_settings({**GROUP, "clinicalQuestionnaire": {"required": False}})


def test_group_rules():
    ok, warnings = validate_plan_settings(
        {**GROUP, "group": {"minInsured": 5, "adhesion": "MANDATORY", "questionnaireWaivedAboveInsured": 20,
                            "premiumBasis": "EXPERIENCE", "premiumPayer": "EMPLOYEE_COPAYS_FAMILY",
                            "profitSharing": {"lossRatioThresholdPct": "65"}}}
    )
    assert ok["group"]["profitSharing"]["lossRatioThresholdPct"] == "65"
    assert "GROUP_MIN_SIZE_ATYPICAL" not in _codes(warnings)
    _, small = validate_plan_settings({**GROUP, "group": {"minInsured": 2}})
    assert "GROUP_MIN_SIZE_ATYPICAL" in _codes(small)
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**GROUP, "group": {"premiumBasis": "GUESS"}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**GROUP, "group": {"profitSharing": {"lossRatioThresholdPct": "120"}}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "group": {"minInsured": 5}})


def test_participation_options_follow_higher_participation_lower_premium():
    """PDF: "Quanto maior a participação escolhida, menor o prémio"."""
    settings = {**INDIVIDUAL, "participationOptions": copy.deepcopy(PARTICIPATION_OPTIONS), "participationOption": "B"}
    validate_plan_settings(settings)

    bad_premium = copy.deepcopy(settings)
    for option in bad_premium["participationOptions"]:
        if option["code"] == "C":
            option["premiumAdjustmentPct"] = "5"  # mais participação mas prémio mais caro
    with pytest.raises(InvalidPlanSettingsError, match="lower premium"):
        validate_plan_settings(bad_premium)

    bad_deductible = copy.deepcopy(settings)
    for option in bad_deductible["participationOptions"]:
        if option["code"] == "D":
            option["annualDeductible"] = "1000"  # franquia menor que a da opção C
    with pytest.raises(InvalidPlanSettingsError, match="annualDeductible"):
        validate_plan_settings(bad_deductible)

    bad_selected = {**settings, "participationOption": "F"}
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings(bad_selected)
    missing = {**INDIVIDUAL, "participationOption": "B"}
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings(missing)

    only_e_cheaper = copy.deepcopy(settings)
    for option in only_e_cheaper["participationOptions"]:
        if option["code"] == "E":
            option["premiumAdjustmentPct"] = "-5"  # mais caro que D
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings(only_e_cheaper)


def test_pre_existing_condition_treatments():
    """PDF: seis tratamentos e onde se aplicam."""
    for mode in ("TOTAL_EXCLUSION", "SPECIFIC_EXCLUSION"):
        validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": mode}})
    validate_plan_settings({**INDIVIDUAL, "tier": "SUPERIOR", "preExistingTreatment": {"mode": "ACCEPTED_WITH_WAITING", "waitingMonths": 12}})
    validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": "ACCEPTED_WITH_LOADING", "loadingPct": "25"}})
    validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": "ACCEPTED_WITH_SUBLIMIT", "sublimitAmount": "500000"}})
    validate_plan_settings({**GROUP, "preExistingTreatment": {"mode": "FULL_ACCEPTANCE"}})

    for waiting in (11, 25):  # só 12 a 24 meses
        with pytest.raises(InvalidPlanSettingsError):
            validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": "ACCEPTED_WITH_WAITING", "waitingMonths": waiting}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": "ACCEPTED_WITH_LOADING"}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": "ACCEPTED_WITH_SUBLIMIT"}})
    # aceitação integral: só Grupo com adesão obrigatória
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": "FULL_ACCEPTANCE"}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**GROUP, "group": {"adhesion": "OPTIONAL"}, "preExistingTreatment": {"mode": "FULL_ACCEPTANCE"}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "preExistingTreatment": {"mode": "WHATEVER"}})


def test_network_geographic_coverage_warning_and_regions():
    """PDF: verificar a cobertura geográfica (Luanda vs províncias)."""
    _, warnings = validate_plan_settings({**INDIVIDUAL, "network": {"regions": []}})
    assert "NETWORK_COVERAGE" in _codes(warnings)
    _, ok = validate_plan_settings({**INDIVIDUAL, "network": {"regions": ["LUANDA", "PROVINCES"]}})
    assert "NETWORK_COVERAGE" not in _codes(ok)
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "network": {"regions": ["MARS"]}})


def test_prior_authorization_and_capital_indexation_settings():
    validate_plan_settings(
        {**INDIVIDUAL, "priorAuthorization": {"internments": True, "highCostExams": True, "scheduledSurgeries": True},
         "capitalIndexation": {"medicalInflationPct": "12.5", "reviewOnRenewal": True}}
    )
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "priorAuthorization": {"internments": "yes"}})
    with pytest.raises(InvalidPlanSettingsError):
        validate_plan_settings({**INDIVIDUAL, "capitalIndexation": {"medicalInflationPct": "-3"}})


# ---------------------------------------------------------- coverage config
def test_capital_forms_and_sublimit_inside_capital():
    config, _ = _cfg(
        "HOSPITALIZATION",
        {
            "limits": [
                {"kind": "ANNUAL_PER_PERSON", "amount": "15000000"},
                {"kind": "PER_ACT_OR_DAY", "label": "Quarto por dia", "amount": "50000"},
                {"kind": "SUBLIMIT", "label": "Próteses intra-operatórias", "amount": "1500000"},
                {"kind": "COINSURANCE_PCT", "pct": "90"},
            ]
        },
        category="BASE",
    )
    assert config["inclusion"] == "INCLUDED"
    with pytest.raises(InvalidCoverageConfigError, match="cannot exceed"):
        _cfg("HOSPITALIZATION", {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "100"}, {"kind": "SUBLIMIT", "label": "x", "amount": "500"}]}, category="BASE")


def test_quantity_limit_needs_count_and_label():
    _cfg("PHYSIOTHERAPY", {"limits": [{"kind": "QUANTITY", "label": "Sessões", "count": 20}]})
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("PHYSIOTHERAPY", {"limits": [{"kind": "QUANTITY", "label": "Sessões"}]})
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("PHYSIOTHERAPY", {"limits": [{"kind": "QUANTITY", "count": 3}]})


def test_single_main_capital_and_per_event_variants():
    with pytest.raises(InvalidCoverageConfigError, match="single main capital"):
        _cfg("OUTPATIENT", {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "1"}, {"kind": "FIXED_AMOUNT", "amount": "2"}]})
    # Parto normal / cesariana: dois capitais por evento com rótulos distintos
    _cfg("MATERNITY", {"limits": [{"kind": "PER_EVENT", "label": "Parto normal", "amount": "600000"}, {"kind": "PER_EVENT", "label": "Cesariana", "amount": "1000000"}]})
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("MATERNITY", {"limits": [{"kind": "PER_EVENT", "label": "A", "amount": "1"}, {"kind": "PER_EVENT", "label": "A", "amount": "2"}]})


def test_household_shared_capital_only_in_individual_family():
    """PDF: capital por agregado/partilhado = um capital para toda a família."""
    _cfg("OUTPATIENT", {"limits": [{"kind": "HOUSEHOLD_SHARED", "amount": "3000000"}]})
    with pytest.raises(InvalidCoverageConfigError, match="INDIVIDUAL_FAMILY"):
        _cfg("OUTPATIENT", {"limits": [{"kind": "HOUSEHOLD_SHARED", "amount": "3000000"}]}, settings=GROUP)


def test_unknown_form_and_bad_amounts():
    for limit in ({"kind": "MAGIC", "amount": "1"}, {"kind": "SUBLIMIT", "amount": "1"}, {"kind": "ANNUAL_PER_PERSON", "amount": "-5"}, {"kind": "ANNUAL_PER_PERSON", "amount": 1.5}, {"kind": "ANNUAL_PER_PERSON"}):
        with pytest.raises(InvalidCoverageConfigError):
            _cfg("OUTPATIENT", {"limits": [limit]})


def test_participation_types_and_where_they_apply():
    config, _ = _cfg(
        "OUTPATIENT",
        {
            "participation": {
                "NETWORK": {"type": "COPAY_FIXED", "copayAmount": "5000", "annualDeductible": "50000"},
                "REIMBURSEMENT": {"type": "COINSURANCE", "insurerPct": "80", "insuredAnnualCap": "500000"},
            }
        },
    )
    assert config["participation"]["REIMBURSEMENT"]["insuredAnnualCap"] == "500000"
    # copagamento fixo é na rede convencionada
    with pytest.raises(InvalidCoverageConfigError, match="NETWORK"):
        _cfg("OUTPATIENT", {"participation": {"REIMBURSEMENT": {"type": "COPAY_FIXED", "copayAmount": "5000"}}})
    # teto anual só na comparticipação
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("OUTPATIENT", {"participation": {"NETWORK": {"type": "COPAY_FIXED", "copayAmount": "1", "insuredAnnualCap": "9"}}})
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("OUTPATIENT", {"participation": {"NETWORK": {"type": "COINSURANCE", "insurerPct": "130"}}})
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("OUTPATIENT", {"participation": {"NETWORK": {"type": "NONE", "copayAmount": "5"}}})
    # franquia por evento (hospitalização)
    _cfg("HOSPITALIZATION", {"participation": {"NETWORK": {"type": "NONE", "perEventDeductible": "100000"}}}, category="BASE")


def test_no_participation_coverage_assistance_24h():
    """PDF: sem participação em urgências vitais, evacuação aprovada, assistência 24h."""
    _cfg("ASSISTANCE_24H", {"participation": {"NETWORK": {"type": "NONE"}}})
    with pytest.raises(InvalidCoverageConfigError, match="no participation"):
        _cfg("ASSISTANCE_24H", {"participation": {"NETWORK": {"type": "COPAY_FIXED", "copayAmount": "100"}}})
    _, warnings = _cfg("MEDICAL_EVACUATION", {"participation": {"NETWORK": {"type": "COINSURANCE", "insurerPct": "80"}}})
    assert "EVACUATION_PARTICIPATION" in _codes(warnings)


def test_access_system_mismatch_warnings():
    _, w1 = _cfg("OUTPATIENT", {"participation": {"REIMBURSEMENT": {"type": "COINSURANCE", "insurerPct": "80"}}}, settings={**INDIVIDUAL, "accessSystem": "NETWORK"})
    assert "ACCESS_SYSTEM_MISMATCH" in _codes(w1)
    _, w2 = _cfg("OUTPATIENT", {"participation": {"NETWORK": {"type": "COPAY_FIXED", "copayAmount": "1"}}}, settings=INDIVIDUAL)
    assert "MIXED_NEEDS_BOTH" in _codes(w2)


def test_waiting_periods_and_anti_selection():
    config, _ = _cfg("MATERNITY", {"waitingDays": {"individual": 365, "group": 0, "accidentWaived": True}, "limits": [{"kind": "PER_EVENT", "amount": "1"}]})
    assert config["waitingDays"]["individual"] == 365
    for bad in ({"individual": -1}, {"group": "30"}, {"accidentWaived": "yes"}):
        with pytest.raises(InvalidCoverageConfigError):
            _cfg("MATERNITY", {"waitingDays": bad})
    # PDF "Anti-seleção": carência no parto e na estomatologia
    _, parto = _cfg("MATERNITY", {"limits": [{"kind": "PER_EVENT", "amount": "1"}]})
    _, dental = _cfg("DENTAL", {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "1"}]})
    assert "ANTI_SELECTION" in _codes(parto) and "ANTI_SELECTION" in _codes(dental)
    _, ok = _cfg("MATERNITY", {"waitingDays": {"individual": 300}, "limits": [{"kind": "PER_EVENT", "amount": "1"}]})
    assert "ANTI_SELECTION" not in _codes(ok)


def test_group_mandatory_adhesion_waiting_hint():
    settings = {**GROUP, "waitingRules": {"groupMandatoryEliminatesWaiting": True}}
    _, warnings = _cfg("MATERNITY", {"waitingDays": {"group": 90}, "limits": [{"kind": "PER_EVENT", "amount": "1"}]}, settings=settings)
    assert "GROUP_WAITING" in _codes(warnings)


def test_evacuation_rules_prior_approval_currency_destinations():
    """PDF: aprovação prévia obrigatória, destinos definidos, moeda do capital (Kz ou USD), risco cambial."""
    config, warnings = _cfg("MEDICAL_EVACUATION", {"currency": "USD", "limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "100000"}]})
    assert config["requiresPriorApproval"] is True
    assert {"FX_RISK", "EVACUATION_DESTINATIONS"} <= _codes(warnings)
    with pytest.raises(InvalidCoverageConfigError, match="prior approval"):
        _cfg("MEDICAL_EVACUATION", {"requiresPriorApproval": False})
    with pytest.raises(InvalidCoverageConfigError, match="not allowed"):
        _cfg("OUTPATIENT", {"currency": "USD"})
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("MEDICAL_EVACUATION", {"currency": "EUR"})
    ok, w = _cfg("MEDICAL_EVACUATION", {"destinations": ["Portugal", "Brasil"]})
    assert "EVACUATION_DESTINATIONS" not in _codes(w)


def test_critical_illness_closed_list_and_fixed_capital():
    config, warnings = _cfg("CRITICAL_ILLNESS", {"limits": [{"kind": "FIXED_AMOUNT", "amount": "5000000"}]})
    assert "CLOSED_LIST" in _codes(warnings)
    _cfg("CRITICAL_ILLNESS", {"closedDiseaseList": ["Cancro", "AVC"], "limits": [{"kind": "FIXED_AMOUNT", "amount": "5000000"}]})
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("CRITICAL_ILLNESS", {"closedDiseaseList": []})


def test_hospital_daily_allowance_days_and_time_deductible():
    _, warnings = _cfg("HOSPITAL_DAILY_ALLOWANCE", {"limits": [{"kind": "FIXED_AMOUNT", "amount": "15000", "unit": "PER_DAY"}]})
    assert "ALLOWANCE_DAYS" in _codes(warnings)
    _, ok = _cfg("HOSPITAL_DAILY_ALLOWANCE", {"maxDaysPerYear": 30, "timeDeductibleDays": 2, "limits": [{"kind": "FIXED_AMOUNT", "amount": "15000"}]})
    assert "ALLOWANCE_DAYS" not in _codes(ok)
    _, odd = _cfg("HOSPITAL_DAILY_ALLOWANCE", {"maxDaysPerYear": 45, "limits": [{"kind": "FIXED_AMOUNT", "amount": "15000"}]})
    assert "ALLOWANCE_DAYS" in _codes(odd)
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("HOSPITAL_DAILY_ALLOWANCE", {"maxDaysPerYear": 0})


def test_base_coverage_must_be_included_and_unknown_keys_warn():
    with pytest.raises(InvalidCoverageConfigError, match="mandatory"):
        _cfg("HOSPITALIZATION", {"inclusion": "OPTIONAL"}, category="BASE")
    with pytest.raises(InvalidCoverageConfigError):
        _cfg("OUTPATIENT", {"inclusion": "UNAVAILABLE"})
    # Chaves desconhecidas não bloqueiam: geram aviso UNKNOWN_COVERAGE_FIELDS.
    _, warnings = _cfg("OUTPATIENT", {"surprise": 1})
    assert any(w["code"] == "UNKNOWN_COVERAGE_FIELDS" for w in warnings)
    config, _ = _cfg("OUTPATIENT", {})
    assert config["inclusion"] == "INCLUDED" and config["currency"] == "AOA"


def test_plan_completeness_rules():
    full = [
        {"code": "HOSPITALIZATION", "category": "BASE", "config": {"limits": [{"kind": "ANNUAL_PER_PERSON", "amount": "1"}]}},
        {"code": "AMBULATORY_SURGERY", "category": "BASE", "config": {}},
        {"code": "EMERGENCY", "category": "BASE", "config": {}},
    ]
    assert plan_completeness_issues(segment="GROUP", coverages=full) == []
    no_capital = [{**full[0], "config": {}}, *full[1:]]
    assert {i["code"] for i in plan_completeness_issues(segment=None, coverages=no_capital)} == {"HOSPITALIZATION_CAPITAL"}
    assert {i["code"] for i in plan_completeness_issues(segment=None, coverages=[])} >= {"HOSPITALIZATION_MISSING", "EMERGENCY_MISSING"}


# ------------------------------------------------------------ PDF templates
def test_every_pdf_template_plan_is_valid():
    """The seeded Individual/Grupo plans must satisfy every rule above."""
    for product in build_templates():
        for plan in product["plans"]:
            settings, _ = validate_plan_settings(plan["settings"])
            for coverage in plan["coverages"]:
                definition = CATALOG_BY_CODE[coverage["code"]]
                validate_coverage_config(
                    coverage["config"],
                    benefit_code=coverage["code"],
                    benefit_category=definition["benefit_type"],
                    benefit_definition=definition["definition"],
                    plan_settings=settings,
                )


def test_template_matrix_matches_the_pdf_comparison_table():
    plans = {p["code"]: {c["code"]: c["config"]["inclusion"] for c in p["coverages"]} for prod in build_templates() for p in prod["plans"]}
    base, medio, superior, grupo = plans["IND-BASE"], plans["IND-MEDIO"], plans["IND-SUPERIOR"], plans["GRP-QUADROS"]
    # Ambulatório: O no Base, B no Médio/Superior/Grupo
    assert base["OUTPATIENT"] == "OPTIONAL" and medio["OUTPATIENT"] == "INCLUDED" and grupo["OUTPATIENT"] == "INCLUDED"
    # Medicamentos: não disponível no Base; O no Médio; B no Superior; O no Grupo
    assert "PHARMACY" not in base and medio["PHARMACY"] == "OPTIONAL" and superior["PHARMACY"] == "INCLUDED" and grupo["PHARMACY"] == "OPTIONAL"
    # Parto: — / O / B / B
    assert "MATERNITY" not in base and medio["MATERNITY"] == "OPTIONAL" and superior["MATERNITY"] == "INCLUDED" and grupo["MATERNITY"] == "INCLUDED"
    # Doenças graves: O / O / B / O
    assert (base["CRITICAL_ILLNESS"], medio["CRITICAL_ILLNESS"], superior["CRITICAL_ILLNESS"], grupo["CRITICAL_ILLNESS"]) == ("OPTIONAL", "OPTIONAL", "INCLUDED", "OPTIONAL")
    # Assistência 24h: B / B / B / O
    assert (base["ASSISTANCE_24H"], medio["ASSISTANCE_24H"], superior["ASSISTANCE_24H"], grupo["ASSISTANCE_24H"]) == ("INCLUDED", "INCLUDED", "INCLUDED", "OPTIONAL")
    # Medicinas alternativas: — / — / O / O
    assert "ALTERNATIVE_MEDICINE" not in base and "ALTERNATIVE_MEDICINE" not in medio
    assert superior["ALTERNATIVE_MEDICINE"] == "OPTIONAL" and grupo["ALTERNATIVE_MEDICINE"] == "OPTIONAL"
    # Doenças preexistentes: — / — / O / B
    assert "PRE_EXISTING_CONDITIONS" not in medio and superior["PRE_EXISTING_CONDITIONS"] == "OPTIONAL" and grupo["PRE_EXISTING_CONDITIONS"] == "INCLUDED"
    # Vacinação: — / O / O / O
    assert "VACCINATION" not in base and medio["VACCINATION"] == superior["VACCINATION"] == grupo["VACCINATION"] == "OPTIONAL"
    # Subsídio diário: O em todos
    assert all(p["HOSPITAL_DAILY_ALLOWANCE"] == "OPTIONAL" for p in (base, medio, superior, grupo))
    # Só grupo: malária/doenças endémicas e medicina no trabalho
    assert grupo["ENDEMIC_DISEASES"] == "OPTIONAL" and grupo["OCCUPATIONAL_MEDICINE"] == "OPTIONAL" and "ENDEMIC_DISEASES" not in superior
    # Colaboradores não têm evacuação ("—" no PDF)
    assert "MEDICAL_EVACUATION" not in plans["GRP-COLABORADORES"] and "MEDICAL_EVACUATION" in plans["GRP-ADMINISTRACAO"]


def _limits(plan_code, benefit_code):
    for product in build_templates():
        for plan in product["plans"]:
            if plan["code"] == plan_code:
                for coverage in plan["coverages"]:
                    if coverage["code"] == benefit_code:
                        return {(lim["kind"], lim.get("label")): lim.get("amount") for lim in coverage["config"].get("limits", [])}
    return None


def test_template_capitals_match_the_pdf_tables():
    assert _limits("IND-BASE", "HOSPITALIZATION")[("ANNUAL_PER_PERSON", None)] == "5000000"
    assert _limits("IND-MEDIO", "HOSPITALIZATION")[("ANNUAL_PER_PERSON", None)] == "15000000"
    assert _limits("IND-SUPERIOR", "HOSPITALIZATION")[("ANNUAL_PER_PERSON", None)] == "40000000"
    assert _limits("IND-BASE", "HOSPITALIZATION")[("PER_ACT_OR_DAY", "Quarto por dia (partilhado)")] == "30000"
    assert _limits("IND-SUPERIOR", "HOSPITALIZATION")[("SUBLIMIT", "Próteses intra-operatórias")] == "4000000"
    assert _limits("IND-MEDIO", "OUTPATIENT")[("PER_ACT_OR_DAY", "Por consulta")] == "25000"
    assert _limits("IND-MEDIO", "MATERNITY") == {("PER_EVENT", "Parto normal"): "600000", ("PER_EVENT", "Cesariana"): "1000000"}
    assert _limits("IND-SUPERIOR", "MATERNITY") == {("PER_EVENT", "Parto normal"): "1500000", ("PER_EVENT", "Cesariana"): "2500000"}
    assert _limits("IND-SUPERIOR", "MEDICAL_EVACUATION")[("ANNUAL_PER_PERSON", None)] == "100000000"
    assert _limits("IND-BASE", "CRITICAL_ILLNESS")[("FIXED_AMOUNT", None)] == "5000000"
    assert _limits("IND-SUPERIOR", "HOSPITAL_DAILY_ALLOWANCE")[("FIXED_AMOUNT", None)] == "25000"
    # Grupo (p.5)
    assert _limits("GRP-COLABORADORES", "HOSPITALIZATION")[("ANNUAL_PER_PERSON", None)] == "10000000"
    assert _limits("GRP-QUADROS", "HOSPITALIZATION")[("ANNUAL_PER_PERSON", None)] == "25000000"
    assert _limits("GRP-ADMINISTRACAO", "HOSPITALIZATION")[("ANNUAL_PER_PERSON", None)] == "60000000"
    assert _limits("GRP-ADMINISTRACAO", "MEDICAL_EVACUATION")[("ANNUAL_PER_PERSON", None)] == "150000000"
    assert _limits("GRP-QUADROS", "OPTICAL")[("ANNUAL_PER_PERSON", None)] == "200000"
    assert _limits("GRP-COLABORADORES", "PHARMACY")[("ANNUAL_PER_PERSON", "Sublimite anual")] == "300000"
    # Medicamentos não existe no Base (matriz), apesar da tabela p.3
    assert _limits("IND-BASE", "PHARMACY") is None
