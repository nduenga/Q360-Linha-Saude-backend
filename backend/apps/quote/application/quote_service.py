"""Quote orchestration (Q360-S6-01..04): create, population, deterministic
pricing + immutable snapshot, and the DRAFT<->READY side effects ART-009's
"Quote Machine" sheet assigns to QT-001/QT-002 (there is no separate manual
"mark ready" command in ART-006 — becoming READY is an automatic side
effect of a successful `priceQuote` whose population has no HARD_STOP/
CONFIG_ERROR eligibility member; any material edit — effectiveDate change,
member added/removed — demotes back to DRAFT and invalidates the pricing
reference, per QT-002's "Atomic Side Effects").

OPEN DECISION — see DECISIONS_TAKEN.md#S06-QUOTE-001 for the judgment
calls this module makes (member status mapping, which members are priced,
default validity days, quote numbering).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.timezone import now as timezone_now

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.eligibility.domain.enums import EligibilityDecision
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.application.auto_resolve import resolve_default_parameter_set_code, resolve_default_rating_table_code
from apps.pricing.application.pricing_engine import calculate_pricing
from apps.pricing.domain.age_band import compute_age_band
from apps.product.domain.enums import PlanStatus
from apps.product.infrastructure.models import Plan, PlanBenefit
from apps.quote.application.numbering_service import next_value
from apps.quote.domain.enums import (
    QuoteDecisionType,
    QuoteMemberStatus,
    QuoteSnapshotType,
    QuoteStatus,
    ReviewTaskStatus,
)
from apps.quote.domain.errors import (
    DuplicateMemberError,
    QuoteStateError,
    ReferencedEntityNotFoundError,
    RowVersionMismatchError,
    SegregationOfDutiesError,
)
from apps.quote.infrastructure.models import (
    AuthorityPolicy,
    Quote,
    QuoteDecision,
    QuoteMember,
    QuoteSnapshot,
    QuoteStateHistory,
    ReviewTask,
)

from apps.client.domain.enums import MemberStatus

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()

_ELIGIBILITY_TO_MEMBER_STATUS = {
    EligibilityDecision.ELIGIBLE.value: QuoteMemberStatus.INCLUDED.value,
    # Angola eligibility has three non-blocking outcomes in addition to
    # the original ART-008 vocabulary.  A loading remains priceable, while
    # documentary/medical cases require an underwriter's review before
    # they can become active on the issued policy.
    EligibilityDecision.ELIGIBLE_WITH_LOADING.value: QuoteMemberStatus.INCLUDED.value,
    EligibilityDecision.PENDING_DOCUMENT.value: QuoteMemberStatus.REFERRAL.value,
    EligibilityDecision.PENDING_MEDICAL_BOARD.value: QuoteMemberStatus.REFERRAL.value,
    EligibilityDecision.WARNING.value: QuoteMemberStatus.INCLUDED.value,
    EligibilityDecision.REFERRAL.value: QuoteMemberStatus.REFERRAL.value,
    EligibilityDecision.HARD_STOP.value: QuoteMemberStatus.EXCLUDED.value,
    EligibilityDecision.CONFIG_ERROR.value: QuoteMemberStatus.EXCLUDED.value,
}

# Members actually submitted to the pricing engine. EXCLUDED (HARD_STOP/
# CONFIG_ERROR at add-time) never enter a price; REFERRAL members are
# still priced provisionally (manual underwriting decides inclusion later,
# see DECISIONS_TAKEN.md#S06-QUOTE-001).
_PRICEABLE_MEMBER_STATUSES = [QuoteMemberStatus.INCLUDED.value, QuoteMemberStatus.REFERRAL.value]


def _plan_content_snapshot(plan: Plan) -> dict:
    """DECISIONS_TAKEN.md#S09-POLICY-001 (ROADMAP_APOLICES.md Fase 1,
    pré-requisito de PO-APO-6): with ProductVersion retired, a Plan is no
    longer immutable once "published" — it can be edited at any time
    (apps.product.application.product_service.update_plan/
    add_plan_benefit/remove_plan_benefit). Every PRICING/SUBMISSION/
    APPROVAL snapshot therefore captures the Plan's full content (not just
    its id), so what a Quote actually contracted stays frozen even if the
    live Plan changes or is later made INACTIVE — the same historical-
    correctness guarantee OD-ANGOLA-004 gave via version immutability
    before this change, now given by the snapshot itself."""
    benefits = [
        {
            "benefitId": str(pb.benefit_id),
            "code": pb.benefit.code,
            "name": pb.benefit.name,
            "category": pb.benefit.benefit_type,
            "configurationJson": pb.configuration_json,
        }
        for pb in PlanBenefit.objects.filter(plan=plan).select_related("benefit").order_by("benefit__code")
    ]
    return {
        "productId": str(plan.product_id),
        "planId": str(plan.id),
        "planCode": plan.code,
        "planName": plan.name,
        "planStatus": plan.status,
        "benefits": benefits,
    }


def _default_valid_until(effective_date: datetime.date) -> datetime.date:
    # OPEN DECISION: no approved document fixes the default quote validity
    # period. Configurable via QUOTE_DEFAULT_VALIDITY_DAYS (settings/env),
    # never hardcoded in business logic — see DECISIONS_TAKEN.md#S06-QUOTE-001.
    days = getattr(settings, "QUOTE_DEFAULT_VALIDITY_DAYS", 30)
    return effective_date + datetime.timedelta(days=days)


def _record_transition(
    quote: Quote, *, from_status: str | None, to_status: str, reason_code: str | None = None,
    reason_text: str | None = None, correlation_id: str | None = None,
) -> None:
    actor = CurrentActorProvider.get()
    QuoteStateHistory.objects.create(
        tenant_id=quote.tenant_id,
        quote=quote,
        from_status=from_status,
        to_status=to_status,
        reason_code=reason_code,
        reason_text=reason_text,
        changed_by=actor.actor_id if actor else "unknown",
        correlation_id=correlation_id,
    )


def create_quote(*, proposer_id: uuid.UUID, plan_id: uuid.UUID, effective_date: datetime.date) -> Quote:
    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()

    proposer = Proposer.objects.filter(id=proposer_id).first()
    plan = Plan.objects.filter(id=plan_id).first()
    if proposer is None or plan is None:
        raise ReferencedEntityNotFoundError("Referenced proposerId or planId does not exist for this tenant")
    if plan.status != PlanStatus.ACTIVE.value:
        # DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): reformulation of the
        # old OD-ANGOLA-009 ("versão antiga nunca inicia negócio novo") now
        # that there is no ProductVersion — an INACTIVE Plan can never
        # start new business, but a Quote already created against it keeps
        # working after it goes INACTIVE (same OD-ANGOLA-004 guarantee,
        # just expressed on the Plan instead of the version).
        raise ReferencedEntityNotFoundError(
            f"Plan {plan_id} is {plan.status}; only an ACTIVE plan can be used to start a new quote"
        )

    # Product Owner decision (2026-09-25): every Quote gets its `COT-N`
    # reference number immediately on creation, not only once APPROVED.
    # Previously this was assigned in decide_quote() and doubled as the
    # OD-ANGOLA-005 "apólice" (policy) number - it now means "cotação"
    # reference number for the whole lifecycle instead; nothing downstream
    # depends on it being null pre-approval (the customer portal login,
    # apps.customer_portal.application.auth_service._resolve_proposer,
    # already filters on `status="APPROVED"` explicitly, not on
    # quote_number being set, so a DRAFT quote's number is still unusable
    # there). Same safe, race-free numbering_service as document numbers.
    quote_number = next_value(sequence_code="QUOTE_NUMBER", period_key=str(effective_date.year), prefix="COT-")

    quote = Quote.objects.create(
        tenant_id=tenant_id.value,
        proposer=proposer,
        plan=plan,
        status=QuoteStatus.DRAFT.value,
        quote_number=quote_number,
        effective_date=effective_date,
        valid_until=_default_valid_until(effective_date),
        created_by=actor.actor_id if actor else "unknown",
    )
    _record_transition(quote, from_status=None, to_status=QuoteStatus.DRAFT.value)
    _audit.record(action="quote.created", entity_type="Quote", entity_id=str(quote.id))
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.CREATED",
        payload={
            "quoteId": str(quote.id),
            "proposerId": str(proposer_id),
            "productId": str(plan.product_id),
            "planId": str(plan_id),
            "effectiveDate": effective_date.isoformat(),
            "status": QuoteStatus.DRAFT.value,
        },
    )
    return quote


def _demote_to_draft_if_ready(quote: Quote) -> None:
    """QT-002 side effect: any material population/date edit invalidates a
    READY quote's readiness and its pricing reference."""
    if quote.status != QuoteStatus.READY.value:
        return
    updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.READY.value).update(
        status=QuoteStatus.DRAFT.value, latest_pricing_run=None, row_version=quote.row_version + 1
    )
    if updated:
        quote.refresh_from_db()
        _record_transition(quote, from_status=QuoteStatus.READY.value, to_status=QuoteStatus.DRAFT.value, reason_code="MATERIAL_EDIT")


def add_quote_member(*, quote: Quote, member_id: uuid.UUID, correlation_id: str | None) -> Quote:
    if quote.status not in (QuoteStatus.DRAFT.value, QuoteStatus.READY.value):
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; members can only be edited while DRAFT or READY")

    member = InsuredMember.objects.filter(id=member_id).first()
    if member is None:
        raise ReferencedEntityNotFoundError(f"memberId {member_id} does not exist for this tenant")
    if member.proposer_id != quote.proposer_id:
        raise ReferencedEntityNotFoundError(
            f"memberId {member_id} does not belong to the proposer associated with quote {quote.id}"
        )
    if member.status != MemberStatus.ACTIVE.value:
        raise ReferencedEntityNotFoundError(
            f"memberId {member_id} is {member.status} and cannot be added to a quote"
        )

    evaluation = EvaluateEligibilityUseCase().execute(
        proposer_id=quote.proposer_id,
        member_id=member.id,
        plan_id=quote.plan_id,
        effective_date=quote.effective_date,
        context={},
        correlation_id=correlation_id,
    )
    member_status = _ELIGIBILITY_TO_MEMBER_STATUS[evaluation.decision]

    try:
        with transaction.atomic():
            QuoteMember.objects.create(
                tenant_id=quote.tenant_id,
                quote=quote,
                member=member,
                status=member_status,
                eligibility_evaluation=evaluation,
            )
    except IntegrityError as exc:
        raise DuplicateMemberError(f"Member {member_id} is already associated with quote {quote.id}") from exc

    _demote_to_draft_if_ready(quote)
    _audit.record(
        action="quote.member_added",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata={"memberId": str(member_id), "eligibilityDecision": evaluation.decision, "quoteMemberStatus": member_status},
    )
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.POPULATION.UPDATED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "changeType": "MEMBER_ADDED",
            "memberId": str(member_id),
            "eligibilityDecision": evaluation.decision,
            "quoteMemberStatus": member_status,
        },
    )
    quote.refresh_from_db()
    return quote


def remove_quote_member(*, quote: Quote, member_id: uuid.UUID) -> None:
    if quote.status not in (QuoteStatus.DRAFT.value, QuoteStatus.READY.value):
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; members can only be edited while DRAFT or READY")

    deleted, _ = QuoteMember.objects.filter(quote=quote, member_id=member_id).delete()
    if deleted == 0:
        raise ReferencedEntityNotFoundError(f"Member {member_id} is not associated with quote {quote.id}")

    _demote_to_draft_if_ready(quote)
    _audit.record(action="quote.member_removed", entity_type="Quote", entity_id=str(quote.id), metadata={"memberId": str(member_id)})
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.POPULATION.UPDATED",
        payload={
            "quoteId": str(quote.id),
            "changeType": "MEMBER_REMOVED",
            "memberId": str(member_id),
        },
    )


def update_quote(*, quote: Quote, effective_date: datetime.date, row_version: int) -> Quote:
    was_ready = quote.status == QuoteStatus.READY.value
    new_status = QuoteStatus.DRAFT.value if was_ready else quote.status
    updated = Quote.objects.filter(id=quote.id, row_version=row_version).update(
        effective_date=effective_date,
        valid_until=_default_valid_until(effective_date),
        status=new_status,
        latest_pricing_run=None if was_ready else quote.latest_pricing_run_id,
        row_version=row_version + 1,
    )
    if updated == 0:
        raise RowVersionMismatchError(f"Quote {quote.id} rowVersion {row_version} does not match the current version")
    quote.refresh_from_db()
    if was_ready:
        _record_transition(quote, from_status=QuoteStatus.READY.value, to_status=QuoteStatus.DRAFT.value, reason_code="MATERIAL_EDIT")
    _audit.record(action="quote.updated", entity_type="Quote", entity_id=str(quote.id), metadata={"rowVersion": quote.row_version})
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.POPULATION.UPDATED",
        payload={
            "quoteId": str(quote.id),
            "changeType": "EFFECTIVE_DATE_UPDATED",
            "effectiveDate": effective_date.isoformat(),
            "rowVersion": quote.row_version,
        },
    )
    return quote


def price_quote(*, quote: Quote, recalculate: bool, correlation_id: str | None):
    if quote.status not in (QuoteStatus.DRAFT.value, QuoteStatus.READY.value):
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; pricing can only run while DRAFT or READY")

    if not recalculate and quote.latest_pricing_run_id and quote.latest_pricing_run.status == "CALCULATED":
        return quote.latest_pricing_run

    priceable_member_ids = list(
        quote.members.filter(status__in=_PRICEABLE_MEMBER_STATUSES).values_list("member_id", flat=True)
    )
    members_by_id = {
        m.id: m for m in InsuredMember.objects.filter(id__in=priceable_member_ids)
    }

    rating_table_code = resolve_default_rating_table_code(effective_date=quote.effective_date)
    parameter_set_code = resolve_default_parameter_set_code(effective_date=quote.effective_date)
    rule_version = resolve_pricing_rule_version_optional(effective_date=quote.effective_date)

    context = {
        "ratingTableCode": rating_table_code,
        "parameterSetCode": parameter_set_code,
        "members": {
            str(member_id): (
                {"ageBand": band} if (band := compute_age_band(members_by_id[member_id].date_of_birth, quote.effective_date)) else {}
            )
            for member_id in priceable_member_ids
        },
    }
    if rule_version:
        context["ruleVersionCode"] = rule_version

    pricing_run = calculate_pricing(
        plan_id=quote.plan_id,
        effective_date=quote.effective_date,
        member_ids=priceable_member_ids,
        context=context,
        correlation_id=correlation_id,
    )

    actor = CurrentActorProvider.get()
    snapshot_json = {
        "plan": _plan_content_snapshot(quote.plan),
        "effectiveDate": quote.effective_date.isoformat(),
        "memberIds": [str(m) for m in priceable_member_ids],
        "context": context,
        "pricingRunId": str(pricing_run.id),
        "totalAmount": str(pricing_run.total_amount),
        "currencyCode": pricing_run.currency_code,
    }
    checksum = hashlib.sha256(json.dumps(snapshot_json, sort_keys=True).encode("utf-8")).hexdigest()
    next_snapshot_no = (
        QuoteSnapshot.objects.filter(quote=quote).order_by("-snapshot_no").values_list("snapshot_no", flat=True).first() or 0
    ) + 1
    QuoteSnapshot.objects.create(
        tenant_id=quote.tenant_id,
        quote=quote,
        snapshot_no=next_snapshot_no,
        snapshot_type=QuoteSnapshotType.PRICING.value,
        pricing_run=pricing_run,
        plan=quote.plan,
        snapshot_json=snapshot_json,
        checksum=checksum,
        created_by=actor.actor_id if actor else "unknown",
    )

    has_blocking_member = quote.members.filter(status=QuoteMemberStatus.EXCLUDED.value).exists()
    Quote.objects.filter(id=quote.id).update(latest_pricing_run=pricing_run, currency_code=pricing_run.currency_code)
    quote.refresh_from_db()
    if quote.status == QuoteStatus.DRAFT.value and not has_blocking_member:
        Quote.objects.filter(id=quote.id, status=QuoteStatus.DRAFT.value).update(status=QuoteStatus.READY.value)
        quote.refresh_from_db()
        _record_transition(quote, from_status=QuoteStatus.DRAFT.value, to_status=QuoteStatus.READY.value, correlation_id=correlation_id)

    _audit.record(
        action="quote.priced",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata={"pricingRunId": str(pricing_run.id), "snapshotNo": next_snapshot_no, "status": quote.status},
    )
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.PRICE.CALCULATED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "pricingRunId": str(pricing_run.id),
            "totalAmount": str(pricing_run.total_amount),
            "currencyCode": pricing_run.currency_code,
            "snapshotNo": next_snapshot_no,
            "status": quote.status,
        },
    )
    return pricing_run


def resolve_pricing_rule_version_optional(*, effective_date: datetime.date) -> str | None:
    """PRICING rule adjustments are optional (Q360-S5-01) — unlike the
    rating table/parameter set, an ambiguous or absent one simply means no
    adjustment is applied, it never blocks pricing."""
    from apps.foundation.infrastructure.models import RuleVersion
    from django.db.models import Q as _Q

    codes = list(
        RuleVersion.objects.filter(
            rule_set__rule_domain="PRICING", status="PUBLISHED", effective_from__lte=effective_date
        )
        .filter(_Q(effective_to__isnull=True) | _Q(effective_to__gte=effective_date))
        .values_list("rule_set__code", flat=True)
        .distinct()
    )
    distinct = sorted(set(codes))
    return distinct[0] if len(distinct) == 1 else None


# ---------------------------------------------------------------------------
# Q360-S7-01..03 — submission, review workspace, decision (approve/reject/
# return). See ART-009 "Quote Machine" (QT-003..006) and "Review Machine"
# (RV-001..005), and DECISIONS_TAKEN.md#S07-REVIEW-001 for the judgment
# calls made here (no START_REVIEW/authority-policy endpoint in ART-006).
# ---------------------------------------------------------------------------


def _create_snapshot(*, quote: Quote, snapshot_type: str) -> QuoteSnapshot:
    """Captures the quote's current (already-calculated) pricing reference
    at a lifecycle milestone — SUBMISSION (QT-003) / APPROVAL (QT-004) —
    without recalculating anything (the snapshot must reflect exactly what
    was priced, not a fresh run)."""
    actor = CurrentActorProvider.get()
    snapshot_json = {
        "status": quote.status,
        "plan": _plan_content_snapshot(quote.plan),
        "effectiveDate": quote.effective_date.isoformat(),
        "latestPricingRunId": str(quote.latest_pricing_run_id) if quote.latest_pricing_run_id else None,
    }
    checksum = hashlib.sha256(json.dumps(snapshot_json, sort_keys=True).encode("utf-8")).hexdigest()
    next_snapshot_no = (
        QuoteSnapshot.objects.filter(quote=quote).order_by("-snapshot_no").values_list("snapshot_no", flat=True).first() or 0
    ) + 1
    return QuoteSnapshot.objects.create(
        tenant_id=quote.tenant_id,
        quote=quote,
        snapshot_no=next_snapshot_no,
        snapshot_type=snapshot_type,
        pricing_run=quote.latest_pricing_run,
        plan=quote.plan,
        snapshot_json=snapshot_json,
        checksum=checksum,
        created_by=actor.actor_id if actor else "unknown",
    )


def submit_quote(*, quote: Quote, row_version: int, correlation_id: str | None) -> Quote:
    """QT-003: READY -> IN_REVIEW. Guard ("valid pricing + immutable
    submission snapshot + prerequisites satisfied") is exactly what
    becoming READY already proved (see price_quote) - submit just requires
    the quote to still be READY."""
    if quote.status != QuoteStatus.READY.value:
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; only a READY quote can be submitted")

    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.READY.value, row_version=row_version).update(
        status=QuoteStatus.IN_REVIEW.value, submitted_by=actor_id, submitted_at=timezone_now(), row_version=row_version + 1
    )
    if updated == 0:
        # Distinguish "someone else changed it" (VERSION-CONFLICT) from
        # "it's no longer READY" (QUOTE-STATE) — re-check which happened.
        quote.refresh_from_db()
        if quote.status != QuoteStatus.READY.value:
            raise QuoteStateError(f"Quote {quote.id} is {quote.status}; only a READY quote can be submitted")
        raise RowVersionMismatchError(f"Quote {quote.id} rowVersion {row_version} does not match the current version")
    quote.refresh_from_db()

    ReviewTask.objects.create(tenant_id=quote.tenant_id, quote=quote, created_by=actor_id)
    _create_snapshot(quote=quote, snapshot_type=QuoteSnapshotType.SUBMISSION.value)
    _record_transition(
        quote, from_status=QuoteStatus.READY.value, to_status=QuoteStatus.IN_REVIEW.value, correlation_id=correlation_id
    )
    _audit.record(action="quote.submitted", entity_type="Quote", entity_id=str(quote.id))
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.SUBMITTED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "submittedBy": actor_id,
            "submittedAt": quote.submitted_at.isoformat() if quote.submitted_at else None,
        },
    )
    return quote


def get_active_review_task(*, quote: Quote) -> ReviewTask | None:
    return quote.review_tasks.order_by("-created_at").first()


def get_quote_history(*, quote: Quote):
    return quote.state_history.order_by("changed_at")


def _resolve_authority_limit(*, effective_date: datetime.date) -> "tuple[AuthorityPolicy | None, str | None]":
    """OD-005 — genuinely open, see DECISIONS_TAKEN.md#S07-REVIEW-001. No
    PUBLISHED AuthorityPolicy means "no configured limit", not fail-closed
    (unlike eligibility): scope (`q360.approve`) + DOC-001 `quote:approve`
    already gate *who* may approve at all; this only narrows *how much*
    once OD-005 names a real policy."""
    from django.db.models import Q as _Q

    policy = (
        AuthorityPolicy.objects.filter(status="PUBLISHED", effective_from__lte=effective_date)
        .filter(_Q(effective_to__isnull=True) | _Q(effective_to__gte=effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )
    if policy is None:
        return None, None
    max_amount = policy.policy_json.get("maxApprovalAmount")
    return policy, max_amount


def decide_quote(
    *,
    quote: Quote,
    decision: str,
    reason_code: str,
    reason_text: str | None,
    row_version: int,
    correlation_id: str | None,
) -> Quote:
    if quote.status != QuoteStatus.IN_REVIEW.value:
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; only an IN_REVIEW quote can be decided")

    review_task = get_active_review_task(quote=quote)
    if review_task is None or review_task.status not in (ReviewTaskStatus.OPEN.value, ReviewTaskStatus.IN_PROGRESS.value):
        raise QuoteStateError(f"Quote {quote.id} has no active review task")

    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"

    # Segregation of duties (Q360-S7-01 AC "Submitter não aprova"; ART-012
    # V019 `ck_quote_four_eyes` / V023 `ck_decision_four_eyes` enforce this
    # at the DB level for every decision type, not just APPROVE - checked
    # here first for a clean SEC-403 instead of a raw IntegrityError.
    if quote.submitted_by and quote.submitted_by == actor_id:
        raise SegregationOfDutiesError(
            f"Actor {actor_id} submitted quote {quote.id} and cannot decide on it (four-eyes)"
        )

    authority_policy = None
    if decision == QuoteDecisionType.APPROVE.value:
        authority_policy, max_amount = _resolve_authority_limit(effective_date=quote.effective_date)
        if max_amount is not None and quote.latest_pricing_run and quote.latest_pricing_run.total_amount is not None:
            from decimal import Decimal

            if quote.latest_pricing_run.total_amount > Decimal(str(max_amount)):
                raise SegregationOfDutiesError(
                    f"Quote {quote.id} total exceeds the approval authority configured in policy {authority_policy.code}"
                )

    target_status = {
        QuoteDecisionType.APPROVE.value: QuoteStatus.APPROVED.value,
        QuoteDecisionType.REJECT.value: QuoteStatus.REJECTED.value,
        QuoteDecisionType.RETURN.value: QuoteStatus.READY.value,
    }[decision]
    review_target_status = {
        QuoteDecisionType.APPROVE.value: ReviewTaskStatus.DECIDED.value,
        QuoteDecisionType.REJECT.value: ReviewTaskStatus.DECIDED.value,
        QuoteDecisionType.RETURN.value: ReviewTaskStatus.RETURNED.value,
    }[decision]

    with transaction.atomic():
        quote_fields = {"status": target_status, "row_version": row_version + 1}
        if decision == QuoteDecisionType.APPROVE.value:
            quote_fields.update(approved_by=actor_id, approved_at=timezone_now())
            if not quote.quote_number:
                # Product Owner decision (2026-09-25): `quote_number` is
                # now assigned in create_quote() instead, so this only
                # ever fires as a backfill for a Quote created before that
                # change. Sequential test/demo number via the same safe,
                # race-free numbering_service already used for document
                # numbers (DECISIONS_TAKEN.md#S06-QUOTE-001 item 4) — NOT a
                # real ARSEG policy-number format (ART-011 PROH-008 still
                # prohibits inventing one), just enough of a stable,
                # unique identifier for the lookup-by-number flow to work.
                quote_fields["quote_number"] = next_value(
                    sequence_code="QUOTE_NUMBER", period_key=str(quote.effective_date.year), prefix="COT-"
                )
        elif decision == QuoteDecisionType.REJECT.value:
            quote_fields.update(rejected_by=actor_id, rejected_at=timezone_now())
        updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.IN_REVIEW.value, row_version=row_version).update(
            **quote_fields
        )
        if updated == 0:
            quote.refresh_from_db()
            if quote.status != QuoteStatus.IN_REVIEW.value:
                raise QuoteStateError(f"Quote {quote.id} is {quote.status}; only an IN_REVIEW quote can be decided")
            raise RowVersionMismatchError(f"Quote {quote.id} rowVersion {row_version} does not match the current version")

        ReviewTask.objects.filter(id=review_task.id).update(status=review_target_status, decided_at=timezone_now())
        quote.refresh_from_db()

        snapshot = None
        if decision == QuoteDecisionType.APPROVE.value:
            snapshot = _create_snapshot(quote=quote, snapshot_type=QuoteSnapshotType.APPROVAL.value)

        QuoteDecision.objects.create(
            tenant_id=quote.tenant_id,
            quote=quote,
            review_task=review_task,
            authority_policy=authority_policy,
            decision=decision,
            reason_code=reason_code,
            reason_text=reason_text,
            decided_by=actor_id,
            submitted_by=quote.submitted_by,
            snapshot=snapshot,
        )

    from_status = QuoteStatus.IN_REVIEW.value
    _record_transition(
        quote, from_status=from_status, to_status=target_status, reason_code=reason_code, reason_text=reason_text,
        correlation_id=correlation_id,
    )
    _audit.record(
        action=f"quote.decision.{decision.lower()}",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata={"reasonCode": reason_code, "decidedBy": actor_id},
    )
    event_type_map = {
        QuoteDecisionType.APPROVE.value: "QUOTE.APPROVED",
        QuoteDecisionType.REJECT.value: "QUOTE.REJECTED",
        QuoteDecisionType.RETURN.value: "QUOTE.RETURNED",
    }
    outbox_payload = {
        "quoteId": str(quote.id),
        "decision": decision,
        "reasonCode": reason_code,
        "reasonText": reason_text,
        "decidedBy": actor_id,
    }
    if decision == QuoteDecisionType.APPROVE.value:
        outbox_payload["approvedAt"] = quote.approved_at.isoformat() if quote.approved_at else None
    elif decision == QuoteDecisionType.REJECT.value:
        outbox_payload["rejectedAt"] = quote.rejected_at.isoformat() if quote.rejected_at else None
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type=event_type_map[decision],
        correlation_id=correlation_id,
        payload=outbox_payload,
    )
    return quote


# ---------------------------------------------------------------------------
# Q360-S8-03 — cancellation (user-initiated) and expiry (system scheduler).
# Both allowed from the same source set per ART-009's Quote Machine
# (QT-007..010 for CANCEL, QT-011..014 for EXPIRE): DRAFT, READY,
# IN_REVIEW, APPROVED. REJECTED/EXPIRED/CANCELLED are terminal (ART-009
# "Forbidden Transitions").
# ---------------------------------------------------------------------------

CANCELLABLE_QUOTE_STATUSES = (
    QuoteStatus.DRAFT.value,
    QuoteStatus.READY.value,
    QuoteStatus.IN_REVIEW.value,
    QuoteStatus.APPROVED.value,
)


def cancel_quote(*, quote: Quote, reason_code: str, reason_text: str | None, row_version: int, correlation_id: str | None) -> Quote:
    if quote.status not in CANCELLABLE_QUOTE_STATUSES:
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; it cannot be cancelled from this state")

    from_status = quote.status
    updated = Quote.objects.filter(id=quote.id, status=from_status, row_version=row_version).update(
        status=QuoteStatus.CANCELLED.value, cancellation_reason=reason_text or reason_code, row_version=row_version + 1
    )
    if updated == 0:
        quote.refresh_from_db()
        if quote.status not in CANCELLABLE_QUOTE_STATUSES:
            raise QuoteStateError(f"Quote {quote.id} is {quote.status}; it cannot be cancelled from this state")
        raise RowVersionMismatchError(f"Quote {quote.id} rowVersion {row_version} does not match the current version")
    quote.refresh_from_db()

    # QT-009's "Close/void active review task consistently" has no clean
    # target status in ART-012's `ck_review_status` (only OPEN/IN_PROGRESS/
    # DECIDED/RETURNED - none means "voided") - left untouched rather than
    # forcing a semantically wrong value. See DECISIONS_TAKEN.md#S08-DOCUMENT-001.

    _record_transition(
        quote, from_status=from_status, to_status=QuoteStatus.CANCELLED.value, reason_code=reason_code,
        reason_text=reason_text, correlation_id=correlation_id,
    )
    _audit.record(action="quote.cancelled", entity_type="Quote", entity_id=str(quote.id), metadata={"reasonCode": reason_code})
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.CANCELLED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "reasonCode": reason_code,
            "reasonText": reason_text,
        },
    )
    return quote


def expire_quote(*, quote: Quote) -> Quote | None:
    """QT-011..014, actor "System Scheduler" (ART-009 Commands & Authority:
    "No user-supplied actor"). Called by `manage.py expire_quotes` (no
    background task queue exists in this stack - a cron/scheduled-task
    invocation of that command is the deployment's responsibility, same
    "no messaging without a real consumer" posture as everywhere else in
    this project). Returns None (no-op) if the quote isn't actually due."""
    if quote.status not in CANCELLABLE_QUOTE_STATUSES or quote.valid_until is None or quote.valid_until >= datetime.date.today():
        return None

    from_status = quote.status
    updated = Quote.objects.filter(id=quote.id, status=from_status).update(status=QuoteStatus.EXPIRED.value)
    if updated == 0:
        return None
    quote.refresh_from_db()

    _record_transition(quote, from_status=from_status, to_status=QuoteStatus.EXPIRED.value, reason_code="VALIDITY_ELAPSED")
    _audit.record(action="quote.expired", entity_type="Quote", entity_id=str(quote.id))
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.EXPIRED",
        payload={
            "quoteId": str(quote.id),
            "validUntil": quote.valid_until.isoformat() if quote.valid_until else None,
            "fromStatus": from_status,
        },
    )
    return quote
