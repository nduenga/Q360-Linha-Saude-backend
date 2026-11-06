"""Apólices a vencer e criação de renovações em lote."""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.claims.application import summary_service
from apps.foundation.domain.problem import DomainProblem
from apps.policy.infrastructure.models import Policy
from apps.pricing.domain.money import round_amount
from apps.quote.application import quote_lifecycle_service
from apps.quote.infrastructure.models import Quote

_CLOSED_QUOTE = ("CANCELLED", "REJECTED", "EXPIRED")
MAX_BATCH = 100


class _DiscardPreview(Exception):
    """Desfaz a transação da prévia depois de lido o prémio proposto."""


def due_policies(*, days: int):
    today = timezone.localdate()
    return (
        Policy.objects.select_related("proposer", "source_quote__latest_pricing_run")
        .filter(status="ACTIVE", end_date__range=(today, today + datetime.timedelta(days=days)))
        .order_by("end_date", "policy_number")
    )


def _proposed_amount(policy: Policy) -> Decimal | None:
    """Prémio da renovação: percorre o fluxo real numa transação sempre desfeita."""
    amount: Decimal | None = None
    try:
        with transaction.atomic():
            renewal = quote_lifecycle_service.create_renewal(source_policy_id=policy.id, plan_id=None)
            renewal = Quote.objects.select_related("latest_pricing_run").get(id=renewal.id)
            if renewal.latest_pricing_run is not None:
                amount = renewal.latest_pricing_run.total_amount
            raise _DiscardPreview
    except _DiscardPreview:
        pass
    except DomainProblem:
        return None
    return amount


def _loss_ratio(policy: Policy) -> str | None:
    """Sem sinistros nem prémios importados não há rácio a mostrar."""
    try:
        data = summary_service.summary(
            proposer_id=policy.proposer_id, policy_id=policy.id, currency=policy.currency_code, record_audit=False
        )
    except DomainProblem:
        return None
    return data.get("lossRatioPct")


def worklist_row(policy: Policy, *, today: datetime.date | None = None) -> dict[str, Any]:
    today = today or timezone.localdate()
    source_run = policy.source_quote.latest_pricing_run
    current = round_amount(source_run.total_amount) if source_run and source_run.total_amount is not None else None
    draft = (
        Quote.objects.select_related("latest_pricing_run")
        .filter(source_policy_id=policy.id, quote_type="RENEWAL").exclude(status__in=_CLOSED_QUOTE)
        .order_by("-created_at").first()
    )
    if draft is not None:
        proposed = draft.latest_pricing_run.total_amount if draft.latest_pricing_run else None
    else:
        proposed = _proposed_amount(policy)
    proposed = round_amount(proposed) if proposed is not None else None
    change = None
    if current and proposed is not None:
        change = str(((proposed - current) / current * Decimal("100")).quantize(Decimal("0.01")))
    return {
        "policyId": str(policy.id),
        "policyNumber": policy.policy_number,
        "holderName": policy.proposer.display_name,
        "endDate": policy.end_date,
        "daysToEnd": (policy.end_date - today).days,
        "activeMembers": policy.members.filter(status="ACTIVE", exclusion_date__isnull=True).count(),
        "lossRatioPct": _loss_ratio(policy),
        "currencyCode": policy.currency_code,
        "currentPremium": str(current) if current is not None else None,
        "proposedPremium": str(proposed) if proposed is not None else None,
        "changePct": change,
        "renewalQuoteId": str(draft.id) if draft else None,
        "renewalQuoteStatus": draft.status if draft else None,
    }


def create_batch(*, policy_ids: list[uuid.UUID]) -> dict[str, list[dict[str, Any]]]:
    """Cada apólice é tratada à parte: uma recusa não impede as restantes."""
    numbers = dict(Policy.objects.filter(id__in=policy_ids).values_list("id", "policy_number"))
    created: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for policy_id in dict.fromkeys(policy_ids):
        outcome = {"policyId": str(policy_id), "policyNumber": numbers.get(policy_id)}
        try:
            with transaction.atomic():
                renewal = quote_lifecycle_service.create_renewal(source_policy_id=policy_id, plan_id=None)
        except DomainProblem as exc:
            failed.append({**outcome, "reason": str(exc)})
            continue
        created.append({**outcome, "quoteId": str(renewal.id), "quoteNumber": renewal.quote_number, "status": renewal.status})
    return {"created": created, "failed": failed}
