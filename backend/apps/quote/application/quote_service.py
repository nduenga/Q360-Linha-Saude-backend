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

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.eligibility.domain.enums import EligibilityDecision
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.application.auto_resolve import resolve_default_parameter_set_code, resolve_default_rating_table_code
from apps.pricing.application.pricing_engine import calculate_pricing
from apps.pricing.domain.age_band import compute_age_band
from apps.product.infrastructure.models import Plan, ProductVersion
from apps.quote.domain.enums import QuoteMemberStatus, QuoteSnapshotType, QuoteStatus
from apps.quote.domain.errors import DuplicateMemberError, QuoteStateError, ReferencedEntityNotFoundError, RowVersionMismatchError
from apps.quote.infrastructure.models import Quote, QuoteMember, QuoteSnapshot, QuoteStateHistory

_audit = AuditService(DjangoAuditRepositoryAdapter())

_ELIGIBILITY_TO_MEMBER_STATUS = {
    EligibilityDecision.ELIGIBLE.value: QuoteMemberStatus.INCLUDED.value,
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


def create_quote(
    *, proposer_id: uuid.UUID, product_version_id: uuid.UUID, plan_id: uuid.UUID, effective_date: datetime.date
) -> Quote:
    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()

    proposer = Proposer.objects.filter(id=proposer_id).first()
    product_version = ProductVersion.objects.filter(id=product_version_id).first()
    plan = Plan.objects.filter(id=plan_id, product_version_id=product_version_id).first()
    if proposer is None or product_version is None or plan is None:
        raise ReferencedEntityNotFoundError(
            "Referenced proposerId, productVersionId or planId does not exist for this tenant "
            "(or planId does not belong to productVersionId)"
        )

    quote = Quote.objects.create(
        tenant_id=tenant_id.value,
        proposer=proposer,
        product_version=product_version,
        plan=plan,
        status=QuoteStatus.DRAFT.value,
        effective_date=effective_date,
        valid_until=_default_valid_until(effective_date),
        created_by=actor.actor_id if actor else "unknown",
    )
    _record_transition(quote, from_status=None, to_status=QuoteStatus.DRAFT.value)
    _audit.record(action="quote.created", entity_type="Quote", entity_id=str(quote.id))
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

    evaluation = EvaluateEligibilityUseCase().execute(
        proposer_id=quote.proposer_id,
        member_id=member.id,
        product_version_id=quote.product_version_id,
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
        product_version_id=quote.product_version_id,
        plan_id=quote.plan_id,
        effective_date=quote.effective_date,
        member_ids=priceable_member_ids,
        context=context,
        correlation_id=correlation_id,
    )

    actor = CurrentActorProvider.get()
    snapshot_json = {
        "productVersionId": str(quote.product_version_id),
        "planId": str(quote.plan_id),
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
        product_version=quote.product_version,
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
