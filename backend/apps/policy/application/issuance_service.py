"""Policy issuance and activation (ROADMAP_APOLICES.md Fase 3).

PO-APO-1 (2026-09-26): a Quote becomes a contract only when the tomador
signs — never on approval alone. `issue_policy()` is that moment: it
requires an already-`APPROVED` Quote and a real signature, and creates
the Policy in `PENDING_FIRST_PREMIUM` — no coverage exists yet (Decreto
n.º 2/02 art. 17.º: the premium's first fraction is due at the contract's
celebration). `register_first_premium_payment()` is the second, separate
moment (art. 17.º again) that actually starts the risk — `PENDING_FIRST_
PREMIUM` -> `ACTIVE`, with `start_date` computed as the day *after*
whichever of signature/payment happened last (never the same day — see
ROADMAP_APOLICES.md "Início do risco", fraud-proofing against a claim
from the morning of the signing/payment day itself).

Every quantity a business decision (payment deadlines, new-business
tolerance days) is intentionally NOT hardcoded here — Fase 7 (falta de
pagamento) is where those get a real, configurable answer.
"""
from __future__ import annotations

import calendar
import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils.timezone import now as timezone_now

from apps.client.domain.enums import ProposerType
from apps.eligibility.domain.enums import EligibilityDecision
from apps.eligibility.domain.evaluation import AngolaEvidence
from apps.eligibility.infrastructure.rule_repository import parse_config
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.policy.domain.enums import PolicyMemberStatus, PolicyStatus, PolicyType, SignatureMethod
from apps.policy.domain.errors import (
    DuplicatePolicyError,
    InvalidStartDateError,
    PolicyStateError,
    ReferencedEntityNotFoundError,
    RowVersionMismatchError,
)
from apps.policy.infrastructure.models import Policy, PolicyMember, PolicySignature, PremiumInstallment
from apps.quote.application.numbering_service import next_continuous_value
from apps.quote.domain.enums import QuoteMemberStatus, QuoteStatus
from apps.quote.infrastructure.models import Quote, QuoteSnapshot

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()

_INSTALLMENT_COUNT = {"ANUAL": 1, "SEMESTRAL": 2, "TRIMESTRAL": 4, "MENSAL": 12}

# PO-APO-2: a member's own subscription outcome never blocks the rest of
# the policy — it only ever affects this member's own row.
_ELIGIBILITY_TO_POLICY_MEMBER_STATUS = {
    EligibilityDecision.ELIGIBLE.value: PolicyMemberStatus.ACTIVE.value,
    EligibilityDecision.WARNING.value: PolicyMemberStatus.ACTIVE.value,
    EligibilityDecision.ELIGIBLE_WITH_LOADING.value: PolicyMemberStatus.ACTIVE.value,
    EligibilityDecision.PENDING_DOCUMENT.value: PolicyMemberStatus.PENDING.value,
    EligibilityDecision.PENDING_MEDICAL_BOARD.value: PolicyMemberStatus.PENDING.value,
    EligibilityDecision.REFERRAL.value: PolicyMemberStatus.PENDING.value,
    # HARD_STOP/CONFIG_ERROR are never copied at all (see issue_policy).
}


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def issue_policy(
    *,
    quote: Quote,
    signatory_name: str,
    signatory_document_type: str,
    signatory_document_number: str,
    signatory_capacity: str,
    signature_method: str,
    signed_at: datetime.datetime,
    term_months: int,
    payment_frequency: str,
    requested_start_date: datetime.date | None,
    row_version: int,
    correlation_id: str | None,
) -> Policy:
    if quote.status != QuoteStatus.APPROVED.value:
        raise PolicyStateError(f"Quote {quote.id} is {quote.status}; only an APPROVED quote can be signed")
    if quote.valid_until is not None and signed_at.date() > quote.valid_until:
        raise PolicyStateError(f"Quote {quote.id} expired on {quote.valid_until}; a new quote is required")

    if requested_start_date is not None:
        # OD-APO-003: never before the quote's effectiveDate (the tarifa
        # was calculated for that date), and never on/before the
        # signature date itself (fraud-proofing — see module docstring).
        # The other half of the rule (never before the *payment* date) can
        # only be enforced once payment happens — see
        # register_first_premium_payment().
        if requested_start_date < quote.effective_date or requested_start_date <= signed_at.date():
            raise InvalidStartDateError(
                f"requestedStartDate {requested_start_date} must be on/after the quote's effectiveDate "
                f"({quote.effective_date}) and strictly after the signature date ({signed_at.date()})"
            )

    snapshot = (
        QuoteSnapshot.objects.filter(quote=quote, snapshot_type="APPROVAL").order_by("-snapshot_no").first()
    )
    if snapshot is None:
        raise PolicyStateError(f"Quote {quote.id} has no APPROVAL snapshot; cannot determine contracted terms")

    if Policy.objects.filter(source_quote=quote).exists():
        raise DuplicatePolicyError(f"Quote {quote.id} already produced a Policy")

    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"

    policy_type = (
        PolicyType.GROUP.value
        if quote.proposer.proposer_type == ProposerType.ORGANISATION.value
        else PolicyType.INDIVIDUAL.value
    )
    policy_number = next_continuous_value(sequence_code="POLICY_NUMBER", prefix="APO-")

    total_amount = (
        quote.latest_pricing_run.total_amount
        if quote.latest_pricing_run and quote.latest_pricing_run.total_amount is not None
        else None
    )

    try:
        with transaction.atomic():
            updated = Quote.objects.filter(
                id=quote.id, status=QuoteStatus.APPROVED.value, row_version=row_version
            ).update(status=QuoteStatus.BOUND.value, row_version=row_version + 1)
            if updated == 0:
                quote.refresh_from_db()
                if quote.status != QuoteStatus.APPROVED.value:
                    raise PolicyStateError(f"Quote {quote.id} is {quote.status}; only an APPROVED quote can be signed")
                raise RowVersionMismatchError(
                    f"Quote {quote.id} rowVersion {row_version} does not match the current version"
                )

            policy = Policy.objects.create(
                tenant_id=tenant_id.value,
                policy_number=policy_number,
                source_quote=quote,
                contracted_terms_snapshot=snapshot,
                proposer=quote.proposer,
                plan=quote.plan,
                policy_type=policy_type,
                term_months=term_months,
                requested_start_date=requested_start_date,
                status=PolicyStatus.PENDING_FIRST_PREMIUM.value,
                payment_frequency=payment_frequency,
                currency_code=quote.currency_code,
                issued_by=actor_id,
            )
            PolicySignature.objects.create(
                tenant_id=tenant_id.value,
                policy=policy,
                signatory_name=signatory_name,
                signatory_document_type=signatory_document_type,
                signatory_document_number=signatory_document_number,
                signatory_capacity=signatory_capacity,
                signature_method=signature_method,
                signed_at=signed_at,
                registered_by=actor_id,
            )

            for quote_member in quote.members.select_related("eligibility_evaluation").all():
                evaluation = quote_member.eligibility_evaluation
                decision = evaluation.decision if evaluation else None
                member_status = _ELIGIBILITY_TO_POLICY_MEMBER_STATUS.get(decision)
                if member_status is None:
                    # HARD_STOP/CONFIG_ERROR (QuoteMemberStatus.EXCLUDED) —
                    # never copied onto the Policy at all.
                    continue
                pending_reason_code = None
                if member_status == PolicyMemberStatus.PENDING.value and evaluation.evidence_json:
                    pending_reason_code = evaluation.evidence_json[0].get("code")
                PolicyMember.objects.create(
                    tenant_id=tenant_id.value,
                    policy=policy,
                    member_id=quote_member.member_id,
                    status=member_status,
                    pending_reason_code=pending_reason_code,
                    eligibility_evaluation=evaluation,
                    rule_version=evaluation.rule_version if evaluation else None,
                )

            if total_amount is not None:
                count = _INSTALLMENT_COUNT[payment_frequency]
                first_amount = _round2(total_amount / count)
                today = timezone_now().date()
                PremiumInstallment.objects.create(
                    tenant_id=tenant_id.value,
                    policy=policy,
                    installment_no=1,
                    # Provisional bounds — recalculated against the real
                    # start_date once activation determines it (see
                    # register_first_premium_payment).
                    period_from=today,
                    period_to=today,
                    due_date=today,
                    amount=first_amount,
                    currency_code=quote.currency_code or "AOA",
                    status="DUE",
                )

    except (PolicyStateError, RowVersionMismatchError, DuplicatePolicyError):
        raise

    _audit.record(
        action="policy.issued",
        entity_type="Policy",
        entity_id=str(policy.id),
        correlation_id=correlation_id,
        metadata={"quoteId": str(quote.id), "policyNumber": policy.policy_number},
    )
    _outbox.append(
        aggregate_type="Policy",
        aggregate_id=str(policy.id),
        event_type="POLICY.ISSUED",
        correlation_id=correlation_id,
        payload={
            "policyId": str(policy.id),
            "policyNumber": policy.policy_number,
            "quoteId": str(quote.id),
            "proposerId": str(quote.proposer_id),
            "status": policy.status,
        },
    )
    return policy


def _plan_benefit_codes(policy: Policy) -> list[str]:
    """Reads the frozen plan content from the snapshot — never the live
    Plan (DECISIONS_TAKEN.md#S09-POLICY-001 Fase 1: what was contracted
    must never drift with a later Plan edit)."""
    plan_json = (policy.contracted_terms_snapshot.snapshot_json or {}).get("plan") or {}
    return [b["code"] for b in plan_json.get("benefits", []) if b.get("code") and b.get("contracted", True)]


def _coverage_waiting_days(policy: Policy) -> dict[str, int]:
    """Waiting days configured on each contracted coverage of the plan (PDF:
    carência por cobertura, individual vs grupo). Frozen in the snapshot."""
    plan_json = (policy.contracted_terms_snapshot.snapshot_json or {}).get("plan") or {}
    key = "group" if (plan_json.get("settings") or {}).get("segment") == "GROUP" else "individual"
    out: dict[str, int] = {}
    for benefit in plan_json.get("benefits", []):
        if not benefit.get("contracted", True):
            continue
        days = ((benefit.get("configurationJson") or {}).get("waitingDays") or {}).get(key)
        if isinstance(days, int) and days > 0:
            out[benefit["code"]] = days
    return out


def _waiting_period_ends(*, policy: Policy, policy_member: PolicyMember, inclusion_date: datetime.date) -> dict:
    config = parse_config(policy_member.rule_version) if policy_member.rule_version is not None else None
    wp = config.waiting_period if config is not None else None

    evaluation = policy_member.eligibility_evaluation
    context = (evaluation.input_snapshot_json.get("context") if evaluation else None) or {}
    evidence = AngolaEvidence.from_dict(context.get("angola"))
    waived = (
        wp is not None
        and wp.waived_on_verified_portability
        and bool(evidence.previous_policy_number)
        and evidence.previous_policy_continuous
    )
    if waived:
        return {}

    coverage_days = _coverage_waiting_days(policy)
    ends: dict[str, str] = {}
    for code in _plan_benefit_codes(policy):
        # The coverage's own waiting period (plan configuration) wins; the
        # eligibility rule's generic one is the fallback.
        days = coverage_days.get(code)
        if days is None and wp is not None:
            days = wp.default_days_by_benefit_category.get(code, wp.default_days)
        if days and days > 0:
            ends[code] = (inclusion_date + datetime.timedelta(days=days)).isoformat()
    return ends


def register_first_premium_payment(
    *,
    policy: Policy,
    paid_at: datetime.datetime,
    payment_reference: str | None,
    payment_method: str | None,
    row_version: int,
    correlation_id: str | None,
) -> Policy:
    if policy.status != PolicyStatus.PENDING_FIRST_PREMIUM.value:
        raise PolicyStateError(f"Policy {policy.id} is {policy.status}; only PENDING_FIRST_PREMIUM can be activated")

    installment = PremiumInstallment.objects.filter(policy=policy, installment_no=1, status="DUE").first()
    if installment is None:
        raise ReferencedEntityNotFoundError(f"Policy {policy.id} has no DUE first installment")

    signature = PolicySignature.objects.filter(policy=policy).first()
    if signature is None:
        raise PolicyStateError(f"Policy {policy.id} has no signature on record")

    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"

    default_start = max(signature.signed_at.date(), paid_at.date()) + datetime.timedelta(days=1)
    start_date = max(default_start, policy.requested_start_date) if policy.requested_start_date else default_start
    end_date = _add_months(start_date, policy.term_months) - datetime.timedelta(days=1)

    with transaction.atomic():
        updated = Policy.objects.filter(
            id=policy.id, status=PolicyStatus.PENDING_FIRST_PREMIUM.value, row_version=row_version
        ).update(
            status=PolicyStatus.ACTIVE.value,
            start_date=start_date,
            end_date=end_date,
            row_version=row_version + 1,
        )
        if updated == 0:
            policy.refresh_from_db()
            if policy.status != PolicyStatus.PENDING_FIRST_PREMIUM.value:
                raise PolicyStateError(f"Policy {policy.id} is {policy.status}; only PENDING_FIRST_PREMIUM can be activated")
            raise RowVersionMismatchError(
                f"Policy {policy.id} rowVersion {row_version} does not match the current version"
            )

        PremiumInstallment.objects.filter(id=installment.id).update(
            status="PAID",
            paid_at=paid_at,
            payment_reference=payment_reference,
            payment_method=payment_method,
            registered_by=actor_id,
            period_from=start_date,
            period_to=_period_end_for(start_date, policy.payment_frequency),
            due_date=start_date,
        )
        _create_remaining_installments(policy=policy, start_date=start_date, tenant_id=tenant_id.value)

        for policy_member in PolicyMember.objects.filter(policy_id=policy.id, status=PolicyMemberStatus.ACTIVE.value):
            waiting_period_ends = _waiting_period_ends(policy=policy, policy_member=policy_member, inclusion_date=start_date)
            PolicyMember.objects.filter(id=policy_member.id).update(
                inclusion_date=start_date,
                waiting_period_ends_json=waiting_period_ends,
                row_version=policy_member.row_version + 1,
            )

    policy.refresh_from_db()
    _audit.record(
        action="policy.activated",
        entity_type="Policy",
        entity_id=str(policy.id),
        correlation_id=correlation_id,
        metadata={"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
    )
    _outbox.append(
        aggregate_type="Policy",
        aggregate_id=str(policy.id),
        event_type="POLICY.ACTIVATED",
        correlation_id=correlation_id,
        payload={
            "policyId": str(policy.id),
            "policyNumber": policy.policy_number,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "status": policy.status,
        },
    )
    return policy


def _add_months(date_value: datetime.date, months: int) -> datetime.date:
    month_index = date_value.month - 1 + months
    year = date_value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date_value.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _period_end_for(start_date: datetime.date, payment_frequency: str) -> datetime.date:
    months_per_installment = {"ANUAL": 12, "SEMESTRAL": 6, "TRIMESTRAL": 3, "MENSAL": 1}[payment_frequency]
    return _add_months(start_date, months_per_installment) - datetime.timedelta(days=1)


def _create_remaining_installments(*, policy: Policy, start_date: datetime.date, tenant_id: uuid.UUID) -> None:
    count = _INSTALLMENT_COUNT[policy.payment_frequency]
    if count <= 1 or policy.currency_code is None:
        return
    months_per_installment = {"ANUAL": 12, "SEMESTRAL": 6, "TRIMESTRAL": 3, "MENSAL": 1}[policy.payment_frequency]
    total_amount = PremiumInstallment.objects.filter(policy=policy, installment_no=1).first()
    if total_amount is None:
        return
    per_installment_amount = total_amount.amount
    for index in range(2, count + 1):
        period_from = _add_months(start_date, months_per_installment * (index - 1))
        period_to = _add_months(period_from, months_per_installment) - datetime.timedelta(days=1)
        PremiumInstallment.objects.create(
            tenant_id=tenant_id,
            policy=policy,
            installment_no=index,
            period_from=period_from,
            period_to=period_to,
            due_date=period_from,
            amount=per_installment_amount,
            currency_code=policy.currency_code,
            status="DUE",
        )
