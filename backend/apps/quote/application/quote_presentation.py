"""Estado da cotação como o utilizador o conhece (Manual visual v2, cap. 22).

`Devolvida` e `Aceite` não são valores de `quote.status`: derivam do histórico
e dos pedidos de aceitação, sem alterar a máquina de estados.
"""
from __future__ import annotations

from apps.quote.application.quote_service import SUBMIT_UNDONE_REASON
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote


def was_returned(quote: Quote) -> bool:
    latest = quote.state_history.order_by("-changed_at").first()
    return (
        latest is not None
        and latest.from_status == QuoteStatus.IN_REVIEW.value
        and latest.to_status == QuoteStatus.READY.value
        and latest.reason_code != SUBMIT_UNDONE_REASON
    )


def display_status(quote: Quote) -> str:
    if quote.status == QuoteStatus.READY.value and was_returned(quote):
        return "RETURNED"
    if quote.status == QuoteStatus.APPROVED.value:
        from apps.customer_portal.application.requests_service import accepted_quote_ids

        if accepted_quote_ids([quote.id]):
            return "ACCEPTED"
    return quote.status
