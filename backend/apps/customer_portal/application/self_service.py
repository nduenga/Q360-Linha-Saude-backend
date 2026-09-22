"""ROADMAP_PORTAL_CLIENTE.md Fase 1 — "sobretudo composição de serviços
de aplicação já existentes e testados": nenhuma regra de negócio nova
aqui, só resolução scoped-ao-cliente das entidades que os serviços já
existentes (quote, product/benefit, eligibility) já sabem tratar.

Toda a resolução passa por `require_customer_proposer_ids` (fail-closed)
— um `quoteNumber` só é aceite se pertencer a um dos `Proposer` ligados
ao `customer_account` autenticado; nunca se confia num `proposerId`/
`planId`/`productVersionId` vindo do pedido do cliente (esses vêm sempre
do `Quote` já resolvido).
"""
from __future__ import annotations

import uuid

from django.db.models import QuerySet

from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.infrastructure.scoping import require_customer_proposer_ids
from apps.quote.infrastructure.models import Quote


def _scoped_proposer_ids() -> list[uuid.UUID]:
    return [uuid.UUID(pid) for pid in require_customer_proposer_ids()]


def list_my_quotes() -> QuerySet[Quote]:
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return Quote.objects.none()
    return Quote.objects.filter(proposer_id__in=proposer_ids).order_by("-created_at")


def resolve_my_quote(quote_number: str) -> Quote:
    proposer_ids = _scoped_proposer_ids()
    quote = (
        Quote.objects.filter(quote_number=quote_number, proposer_id__in=proposer_ids).first()
        if proposer_ids
        else None
    )
    if quote is None:
        raise PortalResourceNotFoundError("No policy found for this quoteNumber")
    return quote
