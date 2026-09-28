"""Coverage verification (ROADMAP_APOLICES.md Fase 4) — the "day-to-day"
eligibility, distinct from subscription eligibility (`apps.eligibility`).
Pure function, no DB — same discipline as `apps.eligibility.domain.
evaluation.evaluate()` (DOC-004 s9/DOC-000 P-02 determinism): same inputs
always produce the same result.

Checked in this exact order (the first that fails decides — see
ROADMAP_APOLICES.md Fase 4):
  1. POLICY_AWAITING_FIRST_PREMIUM — Policy is PENDING_FIRST_PREMIUM.
  2. POLICY_SUSPENDED_NO_PAYMENT — Policy is SUSPENDED on `on_date`
     (Fase 7 is what ever sets this status; the check itself is built now
     so activating suspension later needs no change here).
  3. POLICY_NOT_IN_FORCE — Policy is TERMINATED/CANCELLED/EXPIRED/RENEWED,
     or `on_date` falls outside [start_date, end_date].
  4. MEMBER_PENDING — the member's own PolicyMember row is PENDING/
     REJECTED (PO-APO-2: never the rest of the policy's problem).
  5. MEMBER_NOT_IN_FORCE — `on_date` falls outside
     [inclusion_date, exclusion_date).
  6. BENEFIT_NOT_IN_PLAN — the requested `benefit_category` was not
     contracted (checked only when a category is actually asked for).
  7. IN_WAITING_PERIOD — `on_date` is still before the benefit's
     `waiting_period_ends_json` entry.
  8. COVERED.
"""
from __future__ import annotations

import dataclasses
import datetime


@dataclasses.dataclass(frozen=True, slots=True)
class PolicyFacts:
    status: str
    start_date: datetime.date | None
    end_date: datetime.date | None
    benefit_codes: frozenset[str]


@dataclasses.dataclass(frozen=True, slots=True)
class PolicyMemberFacts:
    status: str
    pending_reason_code: str | None
    inclusion_date: datetime.date | None
    exclusion_date: datetime.date | None
    waiting_period_ends: dict[str, datetime.date]


@dataclasses.dataclass(frozen=True, slots=True)
class CoverageResult:
    covered: bool
    reason_code: str
    message: str
    waiting_period_ends: datetime.date | None = None


_MESSAGES: dict[str, str] = {
    "POLICY_AWAITING_FIRST_PREMIUM": "A apólice ainda não está activa — falta confirmar o pagamento da 1.ª fracção.",
    "POLICY_SUSPENDED_NO_PAYMENT": "A apólice está suspensa por falta de pagamento.",
    "POLICY_NOT_IN_FORCE": "A apólice não está em vigor nesta data.",
    "MEMBER_PENDING": "Este beneficiário ainda não está activo — falta um documento ou uma decisão pendente.",
    "MEMBER_NOT_IN_FORCE": "Este beneficiário não está coberto nesta data.",
    "BENEFIT_NOT_IN_PLAN": "Esta cobertura não faz parte do plano contratado.",
    "IN_WAITING_PERIOD": "Ainda em período de carência para esta cobertura.",
    "COVERED": "Coberto.",
}


def _not_covered(reason_code: str, *, waiting_period_ends: datetime.date | None = None) -> CoverageResult:
    return CoverageResult(
        covered=False, reason_code=reason_code, message=_MESSAGES[reason_code], waiting_period_ends=waiting_period_ends
    )


_POLICY_TERMINAL_STATUSES = frozenset({"TERMINATED", "CANCELLED", "EXPIRED", "RENEWED"})
_MEMBER_NOT_ACTIVE_STATUSES = frozenset({"PENDING", "REJECTED", "EXCLUDED"})


def check_coverage(
    *,
    policy: PolicyFacts,
    member: PolicyMemberFacts | None,
    on_date: datetime.date,
    benefit_category: str | None,
) -> CoverageResult:
    # 1 — awaiting first premium.
    if policy.status == "PENDING_FIRST_PREMIUM":
        return _not_covered("POLICY_AWAITING_FIRST_PREMIUM")

    # 2 — suspended (Fase 7 sets this; the check is ready regardless).
    if policy.status == "SUSPENDED":
        return _not_covered("POLICY_SUSPENDED_NO_PAYMENT")

    # 3 — not in force (terminal status, or outside the vigência window).
    if policy.status in _POLICY_TERMINAL_STATUSES:
        return _not_covered("POLICY_NOT_IN_FORCE")
    if policy.status != "ACTIVE":
        # Any status this domain does not yet know about fails closed,
        # the same posture apps.eligibility takes for CONFIG_ERROR.
        return _not_covered("POLICY_NOT_IN_FORCE")
    if policy.start_date is None or policy.end_date is None or not (policy.start_date <= on_date <= policy.end_date):
        return _not_covered("POLICY_NOT_IN_FORCE")

    # 4/5 — the member's own row.
    if member is None or member.status in _MEMBER_NOT_ACTIVE_STATUSES:
        return _not_covered("MEMBER_PENDING")
    if member.inclusion_date is None or on_date < member.inclusion_date:
        return _not_covered("MEMBER_NOT_IN_FORCE")
    if member.exclusion_date is not None and on_date >= member.exclusion_date:
        return _not_covered("MEMBER_NOT_IN_FORCE")

    # 6 — the requested benefit was actually contracted.
    if benefit_category is not None and benefit_category not in policy.benefit_codes:
        return _not_covered("BENEFIT_NOT_IN_PLAN")

    # 7 — waiting period, only for the benefit actually being checked.
    if benefit_category is not None:
        ends = member.waiting_period_ends.get(benefit_category)
        if ends is not None and on_date < ends:
            return _not_covered("IN_WAITING_PERIOD", waiting_period_ends=ends)

    # 8 — covered.
    return CoverageResult(covered=True, reason_code="COVERED", message=_MESSAGES["COVERED"])
