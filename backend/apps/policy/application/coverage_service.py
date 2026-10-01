"""Orchestrates apps.policy.domain.coverage.check_coverage against real
`Policy`/`PolicyMember` rows (ROADMAP_APOLICES.md Fase 4)."""
from __future__ import annotations

import datetime

from apps.policy.domain.coverage import CoverageResult, PolicyFacts, PolicyMemberFacts, check_coverage
from apps.policy.domain.errors import ReferencedEntityNotFoundError
from apps.policy.infrastructure.models import Policy, PolicyMember


def _policy_facts(policy: Policy) -> PolicyFacts:
    plan_json = (policy.contracted_terms_snapshot.snapshot_json or {}).get("plan") or {}
    # Only what the customer actually has: an optional ("O") coverage the
    # quote did not select is offered by the plan but not contracted.
    benefit_codes = frozenset(
        b["code"] for b in plan_json.get("benefits", []) if b.get("code") and b.get("contracted", True)
    )
    accident_waived = frozenset(
        b["code"]
        for b in plan_json.get("benefits", [])
        if b.get("code") and b.get("contracted", True) and (b.get("configurationJson") or {}).get("waitingDays", {}).get("accidentWaived")
    )
    return PolicyFacts(
        status=policy.status, start_date=policy.start_date, end_date=policy.end_date, benefit_codes=benefit_codes,
        accident_waived_codes=accident_waived,
    )


def _member_facts(policy_member: PolicyMember | None) -> PolicyMemberFacts | None:
    if policy_member is None:
        return None
    waiting_period_ends = {
        code: datetime.date.fromisoformat(value)
        for code, value in (policy_member.waiting_period_ends_json or {}).items()
    }
    return PolicyMemberFacts(
        status=policy_member.status,
        pending_reason_code=policy_member.pending_reason_code,
        inclusion_date=policy_member.inclusion_date,
        exclusion_date=policy_member.exclusion_date,
        waiting_period_ends=waiting_period_ends,
    )


def get_member_coverage(
    *, policy: Policy, member_id, on_date: datetime.date, benefit_category: str | None, accident: bool = False
) -> CoverageResult:
    policy_member = PolicyMember.objects.filter(policy=policy, member_id=member_id).first()
    if policy_member is None:
        raise ReferencedEntityNotFoundError(f"Member {member_id} is not associated with policy {policy.id}")
    return check_coverage(
        policy=_policy_facts(policy), member=_member_facts(policy_member), on_date=on_date,
        benefit_category=benefit_category, accident=accident,
    )


def get_policy_coverage(
    *, policy: Policy, on_date: datetime.date, benefit_category: str | None, accident: bool = False
) -> list[dict]:
    """No `memberId` given — evaluates every member on the policy (same
    "omit memberId to check all" posture the Portal do Cliente's
    eligibility endpoint already established, see
    apps.customer_portal.interfaces.self_service_views)."""
    results = []
    for policy_member in PolicyMember.objects.filter(policy=policy).select_related("member"):
        result = check_coverage(
            policy=_policy_facts(policy),
            member=_member_facts(policy_member),
            on_date=on_date,
            benefit_category=benefit_category,
            accident=accident,
        )
        results.append({"memberId": str(policy_member.member_id), "result": result})
    return results
