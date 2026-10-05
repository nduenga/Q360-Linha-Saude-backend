"""ROADMAP_PORTAL_CLIENTE.md Fase 1, migrated to Policy in Fase 6
(DECISIONS_TAKEN.md#S09-POLICY-001): "sobretudo composição de serviços de
aplicação já existentes e testados" — nenhuma regra de negócio nova aqui,
só resolução scoped-ao-cliente das entidades que os serviços já
existentes (policy, product/benefit) já sabem tratar.

Toda a resolução passa por `require_customer_proposer_ids` (fail-closed)
— um `policyNumber` só é aceite se pertencer a um dos `Proposer` ligados
ao `customer_account` autenticado; nunca se confia num `proposerId`/
`planId` vindo do pedido do cliente (esses vêm sempre do `Policy` já
resolvido).
"""
from __future__ import annotations

import datetime
import uuid

from django.db.models import QuerySet

from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.infrastructure.scoping import require_customer_proposer_ids
from apps.policy.infrastructure.models import Policy
from apps.pricing.domain.money import round_amount
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote


def _scoped_proposer_ids() -> list[uuid.UUID]:
    return [uuid.UUID(pid) for pid in require_customer_proposer_ids()]


def list_my_policies() -> QuerySet[Policy]:
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return Policy.objects.none()
    return Policy.objects.filter(proposer_id__in=proposer_ids).order_by("-created_at")


def resolve_my_policy(policy_number: str) -> Policy:
    proposer_ids = _scoped_proposer_ids()
    policy = (
        Policy.objects.filter(policy_number=policy_number, proposer_id__in=proposer_ids).first()
        if proposer_ids
        else None
    )
    if policy is None:
        raise PortalResourceNotFoundError("No policy found for this policyNumber")
    return policy


# A DRAFT is still the staff's private work in progress — never shown to the
# customer. Every other status maps to one customer-facing label below.
_PORTAL_QUOTE_STATUS = {
    QuoteStatus.READY.value: "IN_REVIEW",
    QuoteStatus.IN_REVIEW.value: "IN_REVIEW",
    QuoteStatus.APPROVED.value: "AWAITING_SIGNATURE",
    QuoteStatus.BOUND.value: "CONTRACTED",
    QuoteStatus.REJECTED.value: "REJECTED",
    QuoteStatus.EXPIRED.value: "EXPIRED",
    QuoteStatus.CANCELLED.value: "CANCELLED",
}
# Price is only a commitment once the quote was approved; before that it can
# still change, so it is not shown.
_PORTAL_QUOTE_SHOWS_PRICE = {"AWAITING_SIGNATURE", "CONTRACTED", "EXPIRED"}


def portal_quote_status(quote: Quote, today: datetime.date) -> str:
    status = _PORTAL_QUOTE_STATUS.get(quote.status, "IN_REVIEW")
    if status == "AWAITING_SIGNATURE" and quote.valid_until is not None and quote.valid_until < today:
        return "EXPIRED"
    return status


def portal_quote_item(quote: Quote, *, policy_number: str | None, today: datetime.date) -> dict:
    status = portal_quote_status(quote, today)
    run = quote.latest_pricing_run
    shows_price = status in _PORTAL_QUOTE_SHOWS_PRICE and run is not None and run.total_amount is not None
    return {
        "quoteNumber": quote.quote_number,
        "status": status,
        "effectiveDate": quote.effective_date,
        "validUntil": quote.valid_until,
        "product": {"name": quote.plan.product.name} if quote.plan.product else None,
        "plan": {"name": quote.plan.name},
        "totalAmount": str(round_amount(run.total_amount)) if shows_price else None,
        "currencyCode": quote.currency_code if shows_price else None,
        "policyNumber": policy_number,
        "createdAt": quote.created_at,
    }


def list_my_quotes(*, today: datetime.date | None = None) -> list[dict]:
    """Read-only, customer-facing view of the caller's quotes: translated
    status, validity, plan/product and price — nothing internal (rejection or
    cancellation reasons, underwriting notes, loadings)."""
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return []
    today = today or datetime.date.today()
    quotes = list(
        Quote.objects.filter(proposer_id__in=proposer_ids)
        .exclude(status=QuoteStatus.DRAFT.value)
        .select_related("plan__product", "latest_pricing_run")
        .order_by("-created_at")
    )
    policy_numbers = dict(
        Policy.objects.filter(source_quote_id__in=[q.id for q in quotes]).values_list(
            "source_quote_id", "policy_number"
        )
    )
    return [portal_quote_item(q, policy_number=policy_numbers.get(q.id), today=today) for q in quotes]
