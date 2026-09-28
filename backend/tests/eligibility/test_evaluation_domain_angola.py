"""Pure unit tests for the MOTOR_ELEGIBILIDADE.md Fase A additions to
apps.eligibility.domain.evaluation — category rules (CHILD/SPOUSE/
ASCENDANT), corporate overrides, pre-existing condition policy and the
waiting-period info message. No DB — same style as
test_evaluation_domain.py, which covers ELIG-001..010 and is left
untouched by these additions (see the regression test at the bottom).
"""
from __future__ import annotations

import datetime

from apps.eligibility.domain.enums import EligibilityDecision
from apps.eligibility.domain.evaluation import (
    AngolaEvidence,
    EligibilityRuleConfig,
    EvaluationInput,
    PlanFacts,
    evaluate,
)

_PLAN_ACTIVE = PlanFacts(is_active=True)
_EFFECTIVE = datetime.date(2026, 6, 1)

_CHILD_RULE = {
    "CHILD": {
        "maxAgeWithoutProof": 18,
        "maxAgeWithProof": 25,
        "proofDocumentType": "CERTIFICADO_MATRICULA",
    }
}
_SPOUSE_RULE = {
    "SPOUSE": {
        "requiresUnionProofFor": ["UNIAO_DE_FACTO"],
        "proofDocumentType": "HOMOLOGACAO_UNIAO_FACTO",
    }
}
_ASCENDANT_RULE = {
    "ASCENDANT": {
        "requiresCohabitationOrFinancialDependency": True,
    }
}


def _input(**overrides) -> EvaluationInput:
    base = dict(
        member_id="m-1",
        relationship_code="FILHO",
        date_of_birth=datetime.date(2005, 1, 1),  # 21 on _EFFECTIVE
        plan_id="plan-1",
        effective_date=_EFFECTIVE,
        relationship_category="CHILD",
    )
    base.update(overrides)
    return EvaluationInput(**base)


def _evaluate(data, config):
    return evaluate(data=data, plan=_PLAN_ACTIVE, config=config)


# --- CHILD ---------------------------------------------------------------


def test_child_under_max_age_without_proof_is_eligible():
    config = EligibilityRuleConfig(category_rules=_CHILD_RULE)
    decision, _ = _evaluate(_input(date_of_birth=datetime.date(2015, 1, 1)), config)  # 11
    assert decision == EligibilityDecision.ELIGIBLE


def test_child_in_proof_bracket_without_certificate_is_pending_document():
    config = EligibilityRuleConfig(category_rules=_CHILD_RULE)
    decision, messages = _evaluate(_input(), config)  # 21, no evidence
    assert decision == EligibilityDecision.PENDING_DOCUMENT
    assert messages[0].code == "FALTA_CERTIFICADO_MATRICULA"
    assert "rejeitado" not in messages[0].message.lower()


def test_child_in_proof_bracket_with_certificate_is_eligible():
    config = EligibilityRuleConfig(category_rules=_CHILD_RULE)
    decision, _ = _evaluate(
        _input(angola_evidence=AngolaEvidence(has_enrollment_certificate=True)), config
    )
    assert decision == EligibilityDecision.ELIGIBLE


def test_child_above_max_age_with_proof_is_hard_stop():
    config = EligibilityRuleConfig(category_rules=_CHILD_RULE)
    decision, messages = _evaluate(_input(date_of_birth=datetime.date(1995, 1, 1)), config)  # 31
    assert decision == EligibilityDecision.HARD_STOP
    assert messages[0].code == "IDADE_ACIMA_LIMITE_DEPENDENTE"
    assert "25" in messages[0].message


def test_child_without_any_category_rules_configured_is_unaffected():
    """Regression guard: tenants that never configure `categoryRules`
    keep behaving exactly like before Fase A."""
    decision, _ = _evaluate(_input(date_of_birth=datetime.date(1995, 1, 1)), EligibilityRuleConfig())
    assert decision == EligibilityDecision.ELIGIBLE


# --- SPOUSE ----------------------------------------------------------------


def test_spouse_uniao_de_facto_without_homologation_is_pending_document():
    config = EligibilityRuleConfig(category_rules=_SPOUSE_RULE)
    decision, messages = _evaluate(
        _input(relationship_category="SPOUSE", angola_evidence=AngolaEvidence(union_bond_type="UNIAO_DE_FACTO")),
        config,
    )
    assert decision == EligibilityDecision.PENDING_DOCUMENT
    assert messages[0].code == "FALTA_HOMOLOGACAO_UNIAO_FACTO"


def test_spouse_uniao_de_facto_with_homologation_is_eligible():
    config = EligibilityRuleConfig(category_rules=_SPOUSE_RULE)
    decision, _ = _evaluate(
        _input(
            relationship_category="SPOUSE",
            angola_evidence=AngolaEvidence(union_bond_type="UNIAO_DE_FACTO", has_union_homologation_document=True),
        ),
        config,
    )
    assert decision == EligibilityDecision.ELIGIBLE


def test_spouse_civil_marriage_never_requires_union_proof():
    config = EligibilityRuleConfig(category_rules=_SPOUSE_RULE)
    decision, _ = _evaluate(
        _input(relationship_category="SPOUSE", angola_evidence=AngolaEvidence(union_bond_type="CASAMENTO")), config
    )
    assert decision == EligibilityDecision.ELIGIBLE


# --- ASCENDANT ---------------------------------------------------------------


def test_ascendant_without_proof_is_pending_document():
    config = EligibilityRuleConfig(category_rules=_ASCENDANT_RULE)
    decision, messages = _evaluate(_input(relationship_category="ASCENDANT"), config)
    assert decision == EligibilityDecision.PENDING_DOCUMENT
    assert messages[0].code == "FALTA_PROVA_DEPENDENCIA_ASCENDENTE"


def test_ascendant_with_proof_is_eligible():
    config = EligibilityRuleConfig(category_rules=_ASCENDANT_RULE)
    decision, _ = _evaluate(
        _input(
            relationship_category="ASCENDANT",
            angola_evidence=AngolaEvidence(has_cohabitation_or_financial_dependency_proof=True),
        ),
        config,
    )
    assert decision == EligibilityDecision.ELIGIBLE


# --- Corporate overrides ---------------------------------------------------


def test_corporate_override_extends_max_age_with_proof():
    config = EligibilityRuleConfig(
        category_rules=_CHILD_RULE,
        corporate_overrides={"empresa-x": {"categoryRules": {"CHILD": {"maxAgeWithProof": 27}}}},
    )
    # Age 26: HARD_STOP under the general rule (limit 25), ELIGIBLE (proof
    # bracket) under empresa-x's override (limit 27).
    member = _input(date_of_birth=datetime.date(2000, 1, 1))  # 26

    decision_general, _ = _evaluate(member, config)
    assert decision_general == EligibilityDecision.HARD_STOP

    member_org = _input(date_of_birth=datetime.date(2000, 1, 1), organisation_proposer_id="empresa-x")
    decision_override, messages = _evaluate(member_org, config)
    assert decision_override == EligibilityDecision.PENDING_DOCUMENT
    assert messages[0].code == "FALTA_CERTIFICADO_MATRICULA"


def test_corporate_override_for_unrelated_company_does_not_apply():
    config = EligibilityRuleConfig(
        category_rules=_CHILD_RULE,
        corporate_overrides={"empresa-x": {"categoryRules": {"CHILD": {"maxAgeWithProof": 27}}}},
    )
    decision, _ = _evaluate(
        _input(date_of_birth=datetime.date(2000, 1, 1), organisation_proposer_id="empresa-y"), config
    )
    assert decision == EligibilityDecision.HARD_STOP


# --- Pre-existing condition policy -----------------------------------------


def test_pre_existing_condition_loading_is_eligible_with_loading():
    config = EligibilityRuleConfig(
        category_rules=_CHILD_RULE,
        pre_existing_condition_policy=None,
    )
    from apps.eligibility.domain.evaluation import PreExistingConditionPolicy

    config = EligibilityRuleConfig(
        pre_existing_condition_policy=PreExistingConditionPolicy(mode="LOADING", loading_percentage="15.00")
    )
    decision, messages = _evaluate(
        _input(
            date_of_birth=datetime.date(2015, 1, 1),
            angola_evidence=AngolaEvidence(has_pre_existing_condition=True),
        ),
        config,
    )
    assert decision == EligibilityDecision.ELIGIBLE_WITH_LOADING
    assert messages[0].code == "ELIGIBLE_COM_AGRAVAMENTO"
    assert "15.00" in messages[0].message
    assert "rejeitado" not in messages[0].message.lower()


def test_pre_existing_condition_pending_medical_board():
    from apps.eligibility.domain.evaluation import PreExistingConditionPolicy

    config = EligibilityRuleConfig(
        pre_existing_condition_policy=PreExistingConditionPolicy(mode="PENDING_MEDICAL_BOARD")
    )
    decision, messages = _evaluate(
        _input(
            date_of_birth=datetime.date(2015, 1, 1),
            angola_evidence=AngolaEvidence(has_pre_existing_condition=True),
        ),
        config,
    )
    assert decision == EligibilityDecision.PENDING_MEDICAL_BOARD
    assert messages[0].code == "PENDENTE_JUNTA_MEDICA"


def test_no_pre_existing_condition_declared_is_unaffected():
    from apps.eligibility.domain.evaluation import PreExistingConditionPolicy

    config = EligibilityRuleConfig(pre_existing_condition_policy=PreExistingConditionPolicy(mode="LOADING"))
    decision, _ = _evaluate(_input(date_of_birth=datetime.date(2015, 1, 1)), config)
    assert decision == EligibilityDecision.ELIGIBLE


# --- Waiting period (informational) ----------------------------------------


def test_waiting_period_message_attached_when_configured():
    from apps.eligibility.domain.evaluation import WaitingPeriodConfig

    config = EligibilityRuleConfig(waiting_period=WaitingPeriodConfig(default_days=300))
    decision, messages = _evaluate(_input(date_of_birth=datetime.date(2015, 1, 1)), config)
    assert decision == EligibilityDecision.ELIGIBLE
    waiting_messages = [m for m in messages if m.code == "ELIG-WAITING-PERIOD"]
    assert len(waiting_messages) == 1
    assert "300" in waiting_messages[0].message


def test_waiting_period_waived_on_verified_portability():
    from apps.eligibility.domain.evaluation import WaitingPeriodConfig

    config = EligibilityRuleConfig(
        waiting_period=WaitingPeriodConfig(default_days=300, waived_on_verified_portability=True)
    )
    decision, messages = _evaluate(
        _input(
            date_of_birth=datetime.date(2015, 1, 1),
            angola_evidence=AngolaEvidence(previous_policy_number="AP-123", previous_policy_continuous=True),
        ),
        config,
    )
    assert decision == EligibilityDecision.ELIGIBLE
    waiting_messages = [m for m in messages if m.code == "ELIG-WAITING-PERIOD"]
    assert "0" in waiting_messages[0].message


def test_no_waiting_period_configured_produces_no_extra_message():
    decision, messages = _evaluate(_input(date_of_birth=datetime.date(2015, 1, 1)), EligibilityRuleConfig())
    assert decision == EligibilityDecision.ELIGIBLE
    assert all(m.code != "ELIG-WAITING-PERIOD" for m in messages)
