"""Pure unit tests for apps.policy.domain.coverage.check_coverage —
ROADMAP_APOLICES.md Fase 4, one per check in the documented order. No DB.
"""
from __future__ import annotations

import dataclasses
import datetime

from apps.policy.domain.coverage import PolicyFacts, PolicyMemberFacts, check_coverage


def dataclasses_replace(obj, **changes):
    return dataclasses.replace(obj, **changes)


_TODAY = datetime.date(2026, 6, 15)

_ACTIVE_POLICY = PolicyFacts(
    status="ACTIVE",
    start_date=datetime.date(2026, 1, 1),
    end_date=datetime.date(2026, 12, 31),
    benefit_codes=frozenset({"HOSPITALIZATION", "MATERNITY"}),
)
_ACTIVE_MEMBER = PolicyMemberFacts(
    status="ACTIVE",
    pending_reason_code=None,
    inclusion_date=datetime.date(2026, 1, 1),
    exclusion_date=None,
    waiting_period_ends={},
)


def test_policy_awaiting_first_premium():
    policy = PolicyFacts(status="PENDING_FIRST_PREMIUM", start_date=None, end_date=None, benefit_codes=frozenset())
    result = check_coverage(policy=policy, member=None, on_date=_TODAY, benefit_category=None)
    assert result.covered is False
    assert result.reason_code == "POLICY_AWAITING_FIRST_PREMIUM"


def test_policy_suspended():
    policy = dataclasses_replace(_ACTIVE_POLICY, status="SUSPENDED")
    result = check_coverage(policy=policy, member=_ACTIVE_MEMBER, on_date=_TODAY, benefit_category=None)
    assert result.reason_code == "POLICY_SUSPENDED_NO_PAYMENT"


def test_policy_terminated():
    policy = dataclasses_replace(_ACTIVE_POLICY, status="CANCELLED")
    result = check_coverage(policy=policy, member=_ACTIVE_MEMBER, on_date=_TODAY, benefit_category=None)
    assert result.reason_code == "POLICY_NOT_IN_FORCE"


def test_policy_active_but_date_outside_vigencia():
    result = check_coverage(policy=_ACTIVE_POLICY, member=_ACTIVE_MEMBER, on_date=datetime.date(2027, 1, 1), benefit_category=None)
    assert result.reason_code == "POLICY_NOT_IN_FORCE"


def test_member_pending():
    member = dataclasses_replace(_ACTIVE_MEMBER, status="PENDING", pending_reason_code="FALTA_CERTIFICADO_MATRICULA")
    result = check_coverage(policy=_ACTIVE_POLICY, member=member, on_date=_TODAY, benefit_category=None)
    assert result.reason_code == "MEMBER_PENDING"


def test_member_missing_entirely_is_pending():
    result = check_coverage(policy=_ACTIVE_POLICY, member=None, on_date=_TODAY, benefit_category=None)
    assert result.reason_code == "MEMBER_PENDING"


def test_member_not_yet_included():
    member = dataclasses_replace(_ACTIVE_MEMBER, inclusion_date=datetime.date(2026, 7, 1))
    result = check_coverage(policy=_ACTIVE_POLICY, member=member, on_date=_TODAY, benefit_category=None)
    assert result.reason_code == "MEMBER_NOT_IN_FORCE"


def test_member_already_excluded():
    member = dataclasses_replace(_ACTIVE_MEMBER, exclusion_date=datetime.date(2026, 6, 1))
    result = check_coverage(policy=_ACTIVE_POLICY, member=member, on_date=_TODAY, benefit_category=None)
    assert result.reason_code == "MEMBER_NOT_IN_FORCE"


def test_member_excluded_today_is_not_covered_on_the_exclusion_date_itself():
    """Half-open interval [inclusion, exclusion) — the exclusion date
    itself is already not covered."""
    member = dataclasses_replace(_ACTIVE_MEMBER, exclusion_date=_TODAY)
    result = check_coverage(policy=_ACTIVE_POLICY, member=member, on_date=_TODAY, benefit_category=None)
    assert result.reason_code == "MEMBER_NOT_IN_FORCE"


def test_benefit_not_contracted():
    result = check_coverage(policy=_ACTIVE_POLICY, member=_ACTIVE_MEMBER, on_date=_TODAY, benefit_category="DENTAL")
    assert result.reason_code == "BENEFIT_NOT_IN_PLAN"


def test_in_waiting_period():
    member = dataclasses_replace(_ACTIVE_MEMBER, waiting_period_ends={"MATERNITY": datetime.date(2026, 10, 1)})
    result = check_coverage(policy=_ACTIVE_POLICY, member=member, on_date=_TODAY, benefit_category="MATERNITY")
    assert result.reason_code == "IN_WAITING_PERIOD"
    assert result.waiting_period_ends == datetime.date(2026, 10, 1)


def test_waiting_period_elapsed_is_covered():
    member = dataclasses_replace(_ACTIVE_MEMBER, waiting_period_ends={"MATERNITY": datetime.date(2026, 1, 1)})
    result = check_coverage(policy=_ACTIVE_POLICY, member=member, on_date=_TODAY, benefit_category="MATERNITY")
    assert result.covered is True
    assert result.reason_code == "COVERED"


def test_covered_with_no_benefit_category_requested():
    """Asking generically ('is this member covered at all today') skips
    the benefit-specific checks (6/7) entirely."""
    result = check_coverage(policy=_ACTIVE_POLICY, member=_ACTIVE_MEMBER, on_date=_TODAY, benefit_category=None)
    assert result.covered is True


def test_determinism_same_input_same_output():
    args = dict(policy=_ACTIVE_POLICY, member=_ACTIVE_MEMBER, on_date=_TODAY, benefit_category="HOSPITALIZATION")
    assert check_coverage(**args) == check_coverage(**args)
