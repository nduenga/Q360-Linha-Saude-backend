"""Coverage service used by the customer portal."""

from __future__ import annotations

import datetime

from apps.policy.domain.coverage import (
    CoverageResult,
    PolicyFacts,
    PolicyMemberFacts,
    check_coverage,
)
from apps.policy.domain.errors import (
    ReferencedEntityNotFoundError,
)
from apps.policy.infrastructure.models import (
    Policy,
    PolicyMember,
)


def _policy_facts(policy: Policy) -> PolicyFacts:
    """Creates the immutable facts required by the domain service."""

    plan_json = (
        policy.contracted_terms_snapshot.snapshot_json or {}
    ).get("plan") or {}

    benefit_codes = frozenset(
        b["code"]
        for b in plan_json.get("benefits", [])
        if b.get("code")
        and b.get("contracted", True)
    )

    accident_waived = frozenset(
        b["code"]
        for b in plan_json.get("benefits", [])
        if (
            b.get("code")
            and b.get("contracted", True)
            and (
                b.get("configurationJson") or {}
            )
            .get("waitingDays", {})
            .get("accidentWaived")
        )
    )

    return PolicyFacts(
        status=policy.status,
        start_date=policy.start_date,
        end_date=policy.end_date,
        benefit_codes=benefit_codes,
        accident_waived_codes=accident_waived,
    )


def _member_facts(
    policy_member: PolicyMember | None,
) -> PolicyMemberFacts | None:
    """Converts the database model to domain facts.

    IMPORTANT:
    We also load the InsuredMember status here.

    This allows the coverage engine to distinguish:
      - member pending
      - member rejected
      - member excluded
      - member globally deactivated
    """

    if policy_member is None:
        return None

    waiting_period_ends = {
        code: datetime.date.fromisoformat(value)
        for code, value in (
            policy_member.waiting_period_ends_json or {}
        ).items()
    }

    return PolicyMemberFacts(
        status=policy_member.status,

        # Estado global do beneficiário.
        member_status=(
            policy_member.member.status
            if policy_member.member is not None
            else None
        ),

        pending_reason_code=(
            policy_member.pending_reason_code
        ),

        inclusion_date=(
            policy_member.inclusion_date
        ),

        exclusion_date=(
            policy_member.exclusion_date
        ),

        waiting_period_ends=waiting_period_ends,
    )


def get_member_coverage(
    *,
    policy: Policy,
    member_id,
    on_date: datetime.date,
    benefit_category: str | None,
    accident: bool = False,
) -> CoverageResult:
    """Checks one beneficiary."""

    policy_member = (
        PolicyMember.objects
        .select_related("member")
        .filter(
            policy=policy,
            member_id=member_id,
        )
        .first()
    )

    if policy_member is None:
        raise ReferencedEntityNotFoundError(
            f"Member {member_id} is not associated "
            f"with policy {policy.id}"
        )

    return check_coverage(
        policy=_policy_facts(policy),
        member=_member_facts(policy_member),
        on_date=on_date,
        benefit_category=benefit_category,
        accident=accident,
    )


def get_policy_coverage(
    *,
    policy: Policy,
    on_date: datetime.date,
    benefit_category: str | None,
    accident: bool = False,
) -> list[dict]:
    """Checks all beneficiaries of the policy."""

    results = []

    policy_members = (
        PolicyMember.objects
        .select_related("member")
        .filter(policy=policy)
    )

    policy_facts = _policy_facts(policy)

    for policy_member in policy_members:

        result = check_coverage(
            policy=policy_facts,
            member=_member_facts(policy_member),
            on_date=on_date,
            benefit_category=benefit_category,
            accident=accident,
        )

        results.append(
            {
                "memberId": str(
                    policy_member.member_id
                ),
                "result": result,
            }
        )

    return results