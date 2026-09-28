"""Pure unit tests for apps.eligibility.domain.evaluation — one per
ART-008 Rule Matrix row (ELIG-001..ELIG-010). No DB, no Django settings
needed beyond what pytest-django wires up for imports.

DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26): ELIG-006
("product version not effective") was retired along with ProductVersion —
a Plan has no date range of its own, only ACTIVE/INACTIVE `status`
(ELIG-007 below covers what ELIG-006 used to).
"""
from __future__ import annotations

import datetime

import pytest

from apps.eligibility.domain.enums import EligibilityDecision
from apps.eligibility.domain.evaluation import (
    Criterion,
    EligibilityRuleConfig,
    EvaluationInput,
    PlanFacts,
    evaluate,
)

_PLAN_ACTIVE = PlanFacts(is_active=True)
_PLAN_INACTIVE = PlanFacts(is_active=False)
_EFFECTIVE = datetime.date(2026, 6, 1)


def _input(**overrides) -> EvaluationInput:
    base = dict(
        member_id="m-1",
        relationship_code="TITULAR",
        date_of_birth=datetime.date(1990, 1, 1),
        plan_id="plan-1",
        effective_date=_EFFECTIVE,
    )
    base.update(overrides)
    return EvaluationInput(**base)


def test_elig_001_missing_member_id_is_hard_stop():
    decision, messages = evaluate(data=_input(member_id=None), plan=_PLAN_ACTIVE, config=None)
    assert decision == EligibilityDecision.HARD_STOP
    assert messages[0].code == "VALIDATION-400"


def test_elig_reference_not_found_when_plan_missing():
    decision, messages = evaluate(data=_input(), plan=None, config=EligibilityRuleConfig())
    assert decision == EligibilityDecision.HARD_STOP
    assert messages[0].code == "ELIG-REFERENCE-NOT-FOUND"


def test_elig_007_plan_inactive():
    decision, messages = evaluate(data=_input(), plan=_PLAN_INACTIVE, config=EligibilityRuleConfig())
    assert decision == EligibilityDecision.HARD_STOP
    assert messages[0].code == "ELIG-PLAN-INACTIVE"


def test_elig_010_no_rule_version_is_config_error():
    decision, messages = evaluate(data=_input(), plan=_PLAN_ACTIVE, config=None)
    assert decision == EligibilityDecision.CONFIG_ERROR
    assert messages[0].code == "ELIG-RULE-MISSING"


def test_elig_002_missing_dob_is_config_error_when_age_rule_configured():
    config = EligibilityRuleConfig(min_entry_age=18)
    decision, messages = evaluate(data=_input(date_of_birth=None), plan=_PLAN_ACTIVE, config=config)
    assert decision == EligibilityDecision.CONFIG_ERROR
    assert messages[0].code == "PRICING-CONFIG"


def test_no_dob_is_fine_when_no_age_rule_configured():
    decision, _ = evaluate(data=_input(date_of_birth=None), plan=_PLAN_ACTIVE, config=EligibilityRuleConfig())
    assert decision == EligibilityDecision.ELIGIBLE


def test_elig_003_age_below_minimum():
    config = EligibilityRuleConfig(min_entry_age=40)
    decision, messages = evaluate(
        data=_input(date_of_birth=datetime.date(2020, 1, 1)),  # ~6 years old
        plan=_PLAN_ACTIVE,
        config=config,
    )
    assert decision == EligibilityDecision.HARD_STOP
    assert messages[0].code == "ELIG-AGE-MIN"


def test_elig_004_age_above_maximum():
    config = EligibilityRuleConfig(max_entry_age=30)
    decision, messages = evaluate(
        data=_input(date_of_birth=datetime.date(1950, 1, 1)),
        plan=_PLAN_ACTIVE,
        config=config,
    )
    assert decision == EligibilityDecision.HARD_STOP
    assert messages[0].code == "ELIG-AGE-MAX"


def test_age_within_bounds_is_eligible():
    config = EligibilityRuleConfig(min_entry_age=18, max_entry_age=65)
    decision, _ = evaluate(
        data=_input(date_of_birth=datetime.date(1990, 1, 1)),
        plan=_PLAN_ACTIVE,
        config=config,
    )
    assert decision == EligibilityDecision.ELIGIBLE


def test_elig_005_relationship_not_allowed():
    config = EligibilityRuleConfig(allowed_relationship_codes=frozenset({"TITULAR", "CONJUGE"}))
    decision, messages = evaluate(data=_input(relationship_code="PRIMO"), plan=_PLAN_ACTIVE, config=config)
    assert decision == EligibilityDecision.HARD_STOP
    assert messages[0].code == "ELIG-RELATIONSHIP"


def test_allowed_relationship_passes():
    config = EligibilityRuleConfig(allowed_relationship_codes=frozenset({"TITULAR"}))
    decision, _ = evaluate(data=_input(relationship_code="TITULAR"), plan=_PLAN_ACTIVE, config=config)
    assert decision == EligibilityDecision.ELIGIBLE


def test_elig_008_referral_criteria_matched():
    config = EligibilityRuleConfig(referral_criteria=(Criterion(min_age=70),))
    decision, messages = evaluate(
        data=_input(date_of_birth=datetime.date(1950, 1, 1)),
        plan=_PLAN_ACTIVE,
        config=config,
    )
    assert decision == EligibilityDecision.REFERRAL
    assert messages[0].code == "ELIG-REFERRAL"


def test_elig_009_warning_criteria_matched():
    config = EligibilityRuleConfig(warning_criteria=(Criterion(relationship_codes=frozenset({"FILHO"})),))
    decision, messages = evaluate(data=_input(relationship_code="FILHO"), plan=_PLAN_ACTIVE, config=config)
    assert decision == EligibilityDecision.WARNING
    assert messages[0].code == "ELIG-WARNING"


def test_default_decision_is_eligible():
    decision, messages = evaluate(data=_input(), plan=_PLAN_ACTIVE, config=EligibilityRuleConfig())
    assert decision == EligibilityDecision.ELIGIBLE
    assert messages[0].code == "ELIG-OK"


def test_determinism_same_input_same_output():
    config = EligibilityRuleConfig(min_entry_age=18, max_entry_age=65)
    args = dict(data=_input(), plan=_PLAN_ACTIVE, config=config)
    first = evaluate(**args)
    second = evaluate(**args)
    assert first == second
