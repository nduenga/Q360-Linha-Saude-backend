"""Copiar e renovar cotações (R1).

  - `clone_quote`: nova cotação com o mesmo proponente, plano, população,
    escolhas, ajustes e decisões de preexistência — para trabalhar variantes
    ou repetir um negócio. A elegibilidade é reavaliada para cada pessoa.
  - `create_renewal`: proposta de renovação de uma **apólice** existente:
    população da apólice (menos quem excede a idade de permanência do plano,
    PDF: renovação até 70–75), escolhas e decisões de preexistência da
    cotação de origem, prémio anterior e período anterior como contexto.
  - `apply_indexation`: o PDF manda rever capitais e tabelas em cada
    renovação face à inflação dos custos médicos — indexa os capitais do plano
    por uma percentagem (por omissão a do plano) como "e se..." da cotação,
    com pré-visualização do impacto no prémio.
"""
from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

from django.db import transaction

from apps.business_config.application.overlays import effective_plan_settings
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.application.plan_dimensions import resolve_plan_pricing_context
from apps.pricing.domain.money import round_amount
from apps.product.domain.plan_settings import decimal_value
from apps.quote.application import quote_service, quote_version_service, simulator_service
from apps.quote.domain.errors import QuoteStateError, ReferencedEntityNotFoundError
from apps.quote.infrastructure.models import Quote, QuoteAdjustment, QuoteMember

_audit = AuditService(DjangoAuditRepositoryAdapter())
_RENEWABLE_POLICY_STATUSES = ("ACTIVE", "EXPIRED")


def _try_reprice(quote: Quote) -> Quote:
    """Best effort: a copy/renewal must exist even if pricing cannot run yet
    (no published tariff, no eligible member...); it simply stays DRAFT."""
    try:
        return simulator_service._reprice(quote)
    except DomainProblem:
        quote.refresh_from_db()
        return quote


def _age_on(date_of_birth: datetime.date | None, on: datetime.date) -> int | None:
    if date_of_birth is None:
        return None
    years = on.year - date_of_birth.year
    if (on.month, on.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


# ------------------------------------------------------------------- clone
def clone_quote(*, quote: Quote, effective_date: datetime.date | None, reason: str | None) -> Quote:
    reason = require_reason(reason)
    actor = CurrentActorProvider.get()
    skipped: list[str] = []
    with transaction.atomic():
        copy = quote_service.create_quote(
            proposer_id=quote.proposer_id, plan_id=quote.plan_id, effective_date=effective_date or quote.effective_date
        )
        for qm in quote.members.order_by("created_at", "id"):
            try:
                quote_service.add_quote_member(quote=copy, member_id=qm.member_id, correlation_id=None)
            except DomainProblem as exc:
                skipped.append(f"{qm.member_id}: {exc}")
        copy.refresh_from_db()

        selection = resolve_plan_pricing_context(plan=copy.plan, selection=quote.selection_json, effective_date=copy.effective_date).selection
        Quote.objects.filter(id=copy.id).update(selection_json=selection)
        for adj in QuoteAdjustment.objects.filter(quote=quote, status="ACTIVE").order_by("applied_at", "id"):
            if adj.member_id and not QuoteMember.objects.filter(quote=copy, member_id=adj.member_id).exists():
                skipped.append(f"adjustment {adj.id}: member not in the copy")
                continue
            QuoteAdjustment.objects.create(
                tenant_id=copy.tenant_id, quote=copy, kind=adj.kind, value=adj.value, scope=adj.scope,
                member_id=adj.member_id, reason=adj.reason, applied_by=actor.actor_id if actor else "unknown",
            )
        for qm in quote.members.exclude(pre_existing_json={}):
            QuoteMember.objects.filter(quote=copy, member_id=qm.member_id).update(pre_existing_json=qm.pre_existing_json)
        copy.refresh_from_db()
        copy = _try_reprice(copy)
        quote_version_service.record_version(quote=copy, source="CLONE", reason=f"Copiada de {quote.quote_number}: {reason}", dedupe=False)
    _audit.record(
        action="quote.cloned",
        entity_type="Quote",
        entity_id=str(copy.id),
        metadata=change_metadata(after={"sourceQuoteId": str(quote.id), "sourceQuoteNumber": quote.quote_number}, reason=reason, skipped=skipped),
    )
    return copy


# ----------------------------------------------------------------- renewal
def create_renewal(
    *, source_policy_id: uuid.UUID, effective_date: datetime.date | None, plan_id: uuid.UUID | None
) -> Quote:
    from apps.policy.infrastructure.models import Policy

    policy = Policy.objects.select_related("source_quote", "plan", "proposer").filter(id=source_policy_id).first()
    if policy is None:
        raise ReferencedEntityNotFoundError(f"A apólice de origem (sourcePolicyId) {source_policy_id} não existe neste tenant")
    if policy.status not in _RENEWABLE_POLICY_STATUSES:
        raise QuoteStateError(f"A apólice {policy.policy_number} está em {policy.status}; só uma apólice ativa (ACTIVE) ou expirada (EXPIRED) pode ser renovada")
    if policy.end_date is None:
        raise QuoteStateError(f"A apólice {policy.policy_number} ainda não tem data de fim e não pode ser renovada")
    if Quote.objects.filter(source_policy_id=policy.id, quote_type="RENEWAL").exclude(status__in=("CANCELLED", "REJECTED", "EXPIRED")).exists():
        raise QuoteStateError(f"A apólice {policy.policy_number} já tem uma cotação de renovação em aberto")

    renewal_date = effective_date or policy.end_date + datetime.timedelta(days=1)
    if effective_date is not None and effective_date < policy.end_date:
        raise QuoteStateError("Uma renovação não pode começar antes do fim do período atual da apólice")
    target_plan_id = plan_id or policy.plan_id
    same_plan = target_plan_id == policy.plan_id

    source_quote = policy.source_quote
    previous_total = None
    if source_quote.latest_pricing_run_id:
        previous_total = str(round_amount(source_quote.latest_pricing_run.total_amount))
    actor = CurrentActorProvider.get()
    carried: list[str] = []
    skipped: list[dict[str, str]] = []

    with transaction.atomic():
        renewal = quote_service.create_quote(
            proposer_id=policy.proposer_id, plan_id=target_plan_id, effective_date=renewal_date
        )
        effective_settings = effective_plan_settings(renewal.plan, renewal_date)
        permanence = (effective_settings.get("permanenceAge") or {}).get("max")
        for policy_member in policy.members.select_related("member").order_by("created_at", "id"):
            if policy_member.status != "ACTIVE" or policy_member.exclusion_date is not None:
                skipped.append({"memberId": str(policy_member.member_id), "reason": "NOT_ACTIVE_IN_POLICY"})
                continue
            age = _age_on(policy_member.member.date_of_birth, renewal_date)
            if permanence is not None and age is not None and age > permanence:
                skipped.append({"memberId": str(policy_member.member_id), "reason": "PERMANENCE_AGE_EXCEEDED", "age": str(age), "limit": str(permanence)})
                continue
            try:
                quote_service.add_quote_member(quote=renewal, member_id=policy_member.member_id, correlation_id=None)
                carried.append(str(policy_member.member_id))
            except DomainProblem as exc:
                skipped.append({"memberId": str(policy_member.member_id), "reason": str(exc)})
        renewal.refresh_from_db()

        selection = {}
        if same_plan and source_quote.selection_json:
            selection = resolve_plan_pricing_context(plan=renewal.plan, selection=source_quote.selection_json, effective_date=renewal.effective_date).selection
        for source_member in source_quote.members.exclude(pre_existing_json={}):
            QuoteMember.objects.filter(quote=renewal, member_id=source_member.member_id).update(
                pre_existing_json=source_member.pre_existing_json
            )
        indexation = effective_settings.get("capitalIndexation") or {}
        deadlines = effective_settings.get("renewalDeadlines") or {}
        rules = effective_settings.get("renewal") or {}
        renewal_json = {
            "sourcePolicyId": str(policy.id),
            "sourcePolicyNumber": policy.policy_number,
            "sourceQuoteId": str(source_quote.id),
            "previousPeriod": {"start": policy.start_date.isoformat() if policy.start_date else None, "end": policy.end_date.isoformat()},
            "previousPremium": {"amount": previous_total, "currencyCode": policy.currency_code},
            "planChanged": not same_plan,
            "carriedMembers": carried,
            "skippedMembers": skipped,
            "capitalIndexation": {"medicalInflationPct": indexation.get("medicalInflationPct"), "applied": False},
            "deadlines": deadlines,
            "rules": rules,
        }
        # `renewal.deadlines.acceptance_days`: prazo para o cliente aceitar a
        # proposta de renovação. A validade da cotação nunca pode ser anterior
        # à data de início (ck_quote_dates), por isso o prazo fica registado
        # em `acceptanceDeadline` e a validade é a mais tardia das duas.
        acceptance_days = deadlines.get("acceptance_days")
        if isinstance(acceptance_days, int) and acceptance_days > 0:
            deadline = datetime.date.today() + datetime.timedelta(days=acceptance_days)
            renewal_json["acceptanceDeadline"] = deadline.isoformat()
        updates: dict[str, Any] = {
            "quote_type": "RENEWAL", "source_policy_id": policy.id, "renewal_json": renewal_json, "selection_json": selection,
        }
        Quote.objects.filter(id=renewal.id).update(**updates)
        renewal.refresh_from_db()
        renewal = _try_reprice(renewal)
        quote_version_service.record_version(quote=renewal, source="RENEWAL", reason=f"Renovação da apólice {policy.policy_number}", dedupe=False)
    _audit.record(
        action="quote.renewal_created",
        entity_type="Quote",
        entity_id=str(renewal.id),
        metadata=change_metadata(after=renewal_json, previousPremium=previous_total, actor=actor.actor_id if actor else None),
    )
    return renewal


# -------------------------------------------------------------- indexation
def _index_amount(raw: Any, factor: Decimal, rounding: Decimal) -> str:
    value = (Decimal(str(raw)) * factor / rounding).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * rounding
    return format(value.normalize(), "f")


def propose_indexation(*, quote: Quote, pct: Decimal, rounding: Decimal) -> dict[str, dict[str, Any]]:
    """`coverageOverrides` that raise every capital/limit amount of the plan's
    coverages by `pct` % (counts, percentages and participation values are
    untouched — only the money limits are indexed)."""
    factor = Decimal("1") + pct / Decimal("100")
    plan_context = resolve_plan_pricing_context(plan=quote.plan, selection=quote.selection_json, effective_date=quote.effective_date)
    overrides: dict[str, dict[str, Any]] = {}
    for coverage in plan_context.coverages:
        config = coverage["configuration"]
        limits = config.get("limits") or []
        if not any("amount" in limit for limit in limits):
            continue
        new_limits = [
            {**limit, "amount": _index_amount(limit["amount"], factor, rounding)} if "amount" in limit else limit
            for limit in limits
        ]
        overrides[coverage["code"]] = {**config, "limits": new_limits}
    return overrides


def apply_indexation(
    *, quote: Quote, pct: str | None, rounding: str | None, reason: str | None, dry_run: bool, render: Callable
) -> dict[str, Any]:
    if quote.quote_type != "RENEWAL":
        raise QuoteStateError("A indexação de capitais aplica-se a cotações de renovação")
    reason = require_reason(reason)
    from apps.foundation.application import system_parameter_service

    configured = (effective_plan_settings(quote.plan, quote.effective_date).get("capitalIndexation") or {}).get("medicalInflationPct")
    if configured is None:
        configured = system_parameter_service.get_stored_value("renewal.default_medical_inflation_pct")
    raw_pct = pct if pct is not None else configured
    if raw_pct is None:
        raise ReferencedEntityNotFoundError("A inflação médica (medicalInflationPct) é obrigatória (o plano não define capitalIndexation.medicalInflationPct)")
    try:
        percentage = decimal_value(raw_pct, "medicalInflationPct", maximum=Decimal("1000"))
        step = decimal_value(rounding if rounding is not None else "1", "roundTo", minimum=Decimal("1"))
    except DomainProblem as exc:
        raise ReferencedEntityNotFoundError(str(exc)) from exc

    overrides = propose_indexation(quote=quote, pct=percentage, rounding=step)
    selection = dict(quote.selection_json or {})
    selection["coverageOverrides"] = {**(selection.get("coverageOverrides") or {}), **overrides}
    preview = simulator_service.preview_quote(quote=quote, selection=selection, extra_adjustments=None, render=render)
    summary = {
        "medicalInflationPct": format(percentage.normalize(), "f"),
        "roundTo": format(step.normalize(), "f"),
        "coverages": {code: cfg["limits"] for code, cfg in overrides.items()},
        "impact": preview["impact"],
    }
    if dry_run:
        return {"dryRun": True, **summary}

    quote, _warnings = simulator_service.set_selection(quote=quote, selection=selection, row_version=quote.row_version)
    renewal_json = dict(quote.renewal_json or {})
    renewal_json["capitalIndexation"] = {
        "medicalInflationPct": summary["medicalInflationPct"],
        "applied": True,
        "reason": reason,
    }
    Quote.objects.filter(id=quote.id).update(renewal_json=renewal_json)
    quote.refresh_from_db()
    _audit.record(
        action="quote.capital_indexation_applied",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(after=summary["coverages"], reason=reason, impact=summary["impact"], medicalInflationPct=summary["medicalInflationPct"]),
    )
    return {"dryRun": False, "quote": quote, **summary}
