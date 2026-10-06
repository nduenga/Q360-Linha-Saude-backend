"""Simulador GTE sobre a cotação: escolhas do cliente, agravamentos e
descontos (R3), "e se..." (R4) e doenças preexistentes por pessoa.

Princípios:
  - **ver o impacto antes de gravar**: tudo o que muda o preço tem uma
    simulação (`dryRun` / `preview`) que corre o *mesmo* motor sem persistir
    nada (`preview_pricing`);
  - **justificar e registar**: aplicar/remover um ajuste ou decidir uma
    preexistência exige motivo (≥10 caracteres) e fica em auditoria com
    `before`/`after`/`impact`;
  - **nunca apagar**: um ajuste removido fica `REMOVED` (autor, data, motivo);
  - **autoridade**: acima do limite da `AuthorityPolicy` publicada
    (`maxAdjustmentPct` / `maxAdjustmentAmount`) só quem pode aprovar
    cotações aplica o ajuste. Sem política publicada não há limite (mesma
    postura do OD-005 para aprovações).
"""
from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from django.db import transaction
from django.utils import timezone

from apps.business_config.application.overlays import effective_plan_settings
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.application.plan_dimensions import resolve_plan_pricing_context
from apps.pricing.application.pricing_engine import preview_pricing
from apps.pricing.domain.commercial_adjustments import KINDS, PERCENT_KINDS, SCOPES
from apps.pricing.domain.money import round_amount
from apps.product.domain.pre_existing import validate_pre_existing_decision
from apps.quote.application import quote_service
from apps.quote.domain.enums import QuoteStatus
from apps.quote.domain.errors import QuoteStateError, ReferencedEntityNotFoundError, RowVersionMismatchError
from apps.quote.infrastructure.models import AuthorityPolicy, Quote, QuoteAdjustment, QuoteMember

_audit = AuditService(DjangoAuditRepositoryAdapter())
_EDITABLE = (QuoteStatus.DRAFT.value, QuoteStatus.READY.value)


class AdjustmentAuthorityError(DomainProblem):
    http_status = 403
    problem_code = "SEC-403"


class AdjustmentNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


def _require_editable(quote: Quote) -> None:
    if quote.status not in _EDITABLE:
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; it can only be changed while DRAFT or READY")


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(round_amount(value))


def _total_render(run) -> dict[str, Any]:
    return {"totalAmount": _money(run.total_amount), "currencyCode": run.currency_code}


def _preview_total(quote: Quote, context: dict, member_ids: list[uuid.UUID], render: Callable = _total_render) -> dict:
    return preview_pricing(
        plan_id=quote.plan_id,
        effective_date=quote.effective_date,
        member_ids=member_ids,
        context=context,
        correlation_id=None,
        render=render,
    )


def _impact(previous: str | None, new: str | None, currency: str | None) -> dict[str, Any]:
    prev, cur = Decimal(previous or "0"), Decimal(new or "0")
    delta = cur - prev
    pct = (delta / prev * Decimal("100")).quantize(Decimal("0.01")) if prev else None
    return {
        "previousTotal": _money(prev),
        "newTotal": _money(cur),
        "delta": _money(delta),
        "deltaPercent": str(pct) if pct is not None else None,
        "currencyCode": currency,
    }


def _reprice(quote: Quote) -> Quote:
    """Material change -> recompute the premium so the quote is consistent
    (and goes back to READY when it was ready before)."""
    if quote.members.exists():
        quote_service.price_quote(quote=quote, recalculate=True, correlation_id=None)
    quote.refresh_from_db()
    return quote


# ------------------------------------------------------------------ selection
def set_selection(*, quote: Quote, selection: dict[str, Any], row_version: int) -> tuple[Quote, list[dict[str, str]]]:
    """Coberturas opcionais escolhidas, opção de participação A–E e
    alterações de capitais/participação ("e se...") da cotação."""
    _require_editable(quote)
    plan_context = resolve_plan_pricing_context(plan=quote.plan, selection=selection, effective_date=quote.effective_date)
    before = quote.selection_json
    with transaction.atomic():
        updated = Quote.objects.filter(id=quote.id, row_version=row_version).update(
            selection_json=plan_context.selection, row_version=row_version + 1
        )
        if updated == 0:
            raise RowVersionMismatchError(f"Quote {quote.id} rowVersion {row_version} does not match the current version")
        quote.refresh_from_db()
        quote_service._demote_to_draft_if_ready(quote)
        quote.refresh_from_db()
    _audit.record(
        action="quote.selection_updated",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(before=before, after=quote.selection_json),
    )
    quote = _reprice(quote)
    return quote, list(plan_context.warnings)


# -------------------------------------------------------------------- preview
def preview_quote(
    *,
    quote: Quote,
    selection: dict[str, Any] | None,
    extra_adjustments: list[dict[str, Any]] | None,
    render: Callable,
) -> dict[str, Any]:
    """"E se...?" without saving: the quote's saved state vs the same state
    with `selection` replaced and/or `extra_adjustments` added. Returns the
    full calculation of the candidate plus the delta against the saved
    state."""
    baseline_context, member_ids = quote_service.build_pricing_context(quote)
    baseline = _preview_total(quote, baseline_context, member_ids)
    if selection is None and not extra_adjustments:
        candidate = _preview_total(quote, baseline_context, member_ids, render)
    else:
        adjustments = quote_service.active_adjustments_for_context(quote)
        for index, spec in enumerate(extra_adjustments or []):
            adjustments.append({"id": f"preview-{index}", **spec})
        candidate_context, _ = quote_service.build_pricing_context(
            quote, selection=selection, adjustments=adjustments
        )
        candidate = _preview_total(quote, candidate_context, member_ids, render)
    candidate["baseline"] = baseline
    candidate["impact"] = _impact(baseline["totalAmount"], candidate["totalAmount"], candidate.get("currencyCode"))
    return candidate


# ---------------------------------------------------------------- adjustments
def _validate_adjustment_spec(quote: Quote, spec: dict[str, Any]) -> dict[str, Any]:
    kind, scope = spec.get("kind"), spec.get("scope", "QUOTE")
    if kind not in KINDS:
        raise ReferencedEntityNotFoundError(f"kind must be one of {list(KINDS)}")
    if scope not in SCOPES:
        raise ReferencedEntityNotFoundError(f"scope must be one of {list(SCOPES)}")
    try:
        value = Decimal(str(spec.get("value")))
    except (InvalidOperation, ValueError) as exc:
        raise ReferencedEntityNotFoundError("value must be a decimal") from exc
    if not value.is_finite() or value <= 0:
        raise ReferencedEntityNotFoundError("value must be greater than zero")
    if kind == "DISCOUNT_PERCENT" and value >= 100:
        raise ReferencedEntityNotFoundError("a percentage discount must be below 100")
    member_id = spec.get("memberId")
    if scope == "MEMBER":
        if not member_id or not QuoteMember.objects.filter(quote=quote, member_id=member_id).exists():
            raise ReferencedEntityNotFoundError("memberId must be a member of this quote when scope is MEMBER")
    elif member_id:
        raise ReferencedEntityNotFoundError("memberId is only allowed when scope is MEMBER")
    return {"kind": kind, "scope": scope, "value": value, "memberId": str(member_id) if member_id else None}


def _authority_limits(quote: Quote) -> dict[str, Any]:
    from django.db.models import Q

    policy = (
        AuthorityPolicy.objects.filter(status="PUBLISHED", effective_from__lte=quote.effective_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=quote.effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )
    return policy.policy_json if policy else {}


def _enforce_authority(quote: Quote, spec: dict[str, Any]) -> bool:
    """Returns True when the adjustment is above the configured limit (the
    caller then needs manager authority: `pricing-config:manage`, held by the
    Administrador and the Gestor de subscrição, not by the Subscritor).
    Raises when it is and they lack it."""
    limits = _authority_limits(quote)
    key = "maxAdjustmentPct" if spec["kind"] in PERCENT_KINDS else "maxAdjustmentAmount"
    limit = limits.get(key)
    if limit is None or spec["value"] <= Decimal(str(limit)):
        return False
    actor = CurrentActorProvider.get()
    if actor is None or not actor.has_permission(Permission.PRICING_CONFIG_MANAGE):
        raise AdjustmentAuthorityError(
            f"A {spec['kind']} of {spec['value']} exceeds the authority limit ({key}={limit}); "
            "a subscription manager must apply it"
        )
    return True


def simulate_adjustment(*, quote: Quote, spec: dict[str, Any]) -> dict[str, Any]:
    """`dryRun`: what the premium would be with this adjustment — nothing
    saved, no pricing run, no audit/outbox."""
    _require_editable(quote)
    clean = _validate_adjustment_spec(quote, spec)
    needs_approval = False
    try:
        needs_approval = _enforce_authority(quote, clean)
    except AdjustmentAuthorityError:
        needs_approval = True  # the simulation is allowed; applying is not
    baseline_context, member_ids = quote_service.build_pricing_context(quote)
    baseline = _preview_total(quote, baseline_context, member_ids)
    adjustments = quote_service.active_adjustments_for_context(quote)
    adjustments.append(
        {"id": "dry-run", "kind": clean["kind"], "value": str(clean["value"]), "scope": clean["scope"],
         "memberId": clean["memberId"], "reason": spec.get("reason")}
    )
    candidate_context, _ = quote_service.build_pricing_context(quote, adjustments=adjustments)
    candidate = _preview_total(quote, candidate_context, member_ids)
    impact = _impact(baseline["totalAmount"], candidate["totalAmount"], candidate.get("currencyCode"))
    return {"dryRun": True, "requiresApproval": needs_approval, **impact}


def apply_adjustment(*, quote: Quote, spec: dict[str, Any], reason: str | None) -> tuple[QuoteAdjustment, Quote]:
    _require_editable(quote)
    reason = require_reason(reason)
    clean = _validate_adjustment_spec(quote, spec)
    exceeds_limit = _enforce_authority(quote, clean)
    actor = CurrentActorProvider.get()

    with transaction.atomic():
        baseline_context, member_ids = quote_service.build_pricing_context(quote)
        baseline = _preview_total(quote, baseline_context, member_ids)
        adjustment = QuoteAdjustment.objects.create(
            tenant_id=quote.tenant_id,
            quote=quote,
            kind=clean["kind"],
            value=clean["value"],
            scope=clean["scope"],
            member_id=clean["memberId"],
            reason=reason,
            applied_by=actor.actor_id if actor else "unknown",
        )
        quote_service._demote_to_draft_if_ready(quote)
        quote.refresh_from_db()
        quote = _reprice(quote)
        new_total = _money(quote.latest_pricing_run.total_amount) if quote.latest_pricing_run_id else None
        impact = _impact(baseline["totalAmount"], new_total, quote.currency_code)
        impact["aboveAuthorityLimit"] = exceeds_limit
        QuoteAdjustment.objects.filter(id=adjustment.id).update(impact_json=impact)
        adjustment.refresh_from_db()
    _audit.record(
        action="quote.adjustment_applied",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(
            after={"adjustmentId": str(adjustment.id), "kind": adjustment.kind, "value": str(adjustment.value),
                   "scope": adjustment.scope, "memberId": clean["memberId"]},
            reason=reason,
            impact=impact,
        ),
    )
    return adjustment, quote


def remove_adjustment(*, quote: Quote, adjustment_id: uuid.UUID, reason: str | None) -> tuple[QuoteAdjustment, Quote]:
    _require_editable(quote)
    reason = require_reason(reason)
    adjustment = QuoteAdjustment.objects.filter(id=adjustment_id, quote=quote).first()
    if adjustment is None:
        raise AdjustmentNotFoundError(f"Adjustment {adjustment_id} does not exist on quote {quote.id}")
    if adjustment.status == "REMOVED":
        raise QuoteStateError(f"Adjustment {adjustment_id} was already removed")
    actor = CurrentActorProvider.get()
    with transaction.atomic():
        baseline_context, member_ids = quote_service.build_pricing_context(quote)
        baseline = _preview_total(quote, baseline_context, member_ids)
        QuoteAdjustment.objects.filter(id=adjustment.id).update(
            status="REMOVED",
            removed_by=actor.actor_id if actor else "unknown",
            removed_at=timezone.now(),
            removed_reason=reason,
        )
        quote_service._demote_to_draft_if_ready(quote)
        quote.refresh_from_db()
        quote = _reprice(quote)
        new_total = _money(quote.latest_pricing_run.total_amount) if quote.latest_pricing_run_id else None
        impact = _impact(baseline["totalAmount"], new_total, quote.currency_code)
        adjustment.refresh_from_db()
    _audit.record(
        action="quote.adjustment_removed",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(
            before={"adjustmentId": str(adjustment.id), "kind": adjustment.kind, "value": str(adjustment.value)},
            reason=reason,
            impact=impact,
        ),
    )
    return adjustment, quote


def list_adjustments(*, quote: Quote, status: str | None = None):
    queryset = QuoteAdjustment.objects.filter(quote=quote).order_by("applied_at", "id")
    if status:
        queryset = queryset.filter(status=status)
    return queryset


# -------------------------------------------------- pre-existing conditions
def set_member_pre_existing(
    *, quote: Quote, member_id: uuid.UUID, decision: dict[str, Any], reason: str | None
) -> tuple[QuoteMember, Quote, list[dict[str, str]]]:
    _require_editable(quote)
    reason = require_reason(reason)
    quote_member = QuoteMember.objects.filter(quote=quote, member_id=member_id).first()
    if quote_member is None:
        raise ReferencedEntityNotFoundError(f"Member {member_id} is not associated with quote {quote.id}")
    clean, warnings = validate_pre_existing_decision(decision, plan_settings=effective_plan_settings(quote.plan, quote.effective_date))
    actor = CurrentActorProvider.get()
    stored = {
        **clean,
        "reason": reason,
        "decidedBy": actor.actor_id if actor else "unknown",
        "decidedAt": timezone.now().isoformat(),
    }
    before = quote_member.pre_existing_json or None
    with transaction.atomic():
        baseline_context, member_ids = quote_service.build_pricing_context(quote)
        baseline = _preview_total(quote, baseline_context, member_ids) if member_ids else None
        QuoteMember.objects.filter(id=quote_member.id).update(pre_existing_json=stored)
        quote_service._demote_to_draft_if_ready(quote)
        quote.refresh_from_db()
        quote = _reprice(quote)
    impact = None
    if baseline is not None and quote.latest_pricing_run_id:
        impact = _impact(baseline["totalAmount"], _money(quote.latest_pricing_run.total_amount), quote.currency_code)
    quote_member.refresh_from_db()
    _audit.record(
        action="quote.member_pre_existing_decided",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(before=before, after=stored, reason=reason, impact=impact, memberId=str(member_id)),
    )
    return quote_member, quote, warnings


def clear_member_pre_existing(*, quote: Quote, member_id: uuid.UUID, reason: str | None) -> Quote:
    _require_editable(quote)
    reason = require_reason(reason)
    quote_member = QuoteMember.objects.filter(quote=quote, member_id=member_id).first()
    if quote_member is None:
        raise ReferencedEntityNotFoundError(f"Member {member_id} is not associated with quote {quote.id}")
    before = quote_member.pre_existing_json or None
    with transaction.atomic():
        QuoteMember.objects.filter(id=quote_member.id).update(pre_existing_json={})
        quote_service._demote_to_draft_if_ready(quote)
        quote.refresh_from_db()
        quote = _reprice(quote)
    _audit.record(
        action="quote.member_pre_existing_cleared",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(before=before, reason=reason, memberId=str(member_id)),
    )
    return quote

