"""Mensagens contextualizadas (PDF s.15): cada conversa pertence a uma
cotação, apólice ou pedido — nunca um chat genérico. A fronteira de acesso do
cliente é o proponente; o backoffice resolve o contexto dentro do inquilino."""
from __future__ import annotations

import uuid
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.application import notifications_service, requests_service
from apps.customer_portal.application.self_service import _scoped_proposer_ids
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.domain.requests import PortalRequestInvalidError
from apps.customer_portal.infrastructure.models import PortalMessage, PortalRequest
from apps.foundation.application.context import CurrentTenantProvider
from apps.policy.infrastructure.models import Policy
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote

CONTEXT_TYPES = ("QUOTE", "POLICY", "REQUEST")
MAX_BODY = 4000


def _tenant_id():
    return CurrentTenantProvider.require().value


def _clean_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise PortalRequestInvalidError("A mensagem (body) é obrigatória")
    if len(body) > MAX_BODY:
        raise PortalRequestInvalidError(f"A mensagem (body) pode ter no máximo {MAX_BODY} caracteres")
    return body


def _check_context_type(context_type: str) -> None:
    if context_type not in CONTEXT_TYPES:
        raise PortalRequestInvalidError(f"O contexto (contextType) tem de ser um de {list(CONTEXT_TYPES)}")


def _resolve(context_type: str, ref: str, *, proposer_ids: list[uuid.UUID] | None):
    """The proposer a conversation belongs to, or 404. `proposer_ids=None`
    means staff (the whole tenant); otherwise the caller's own proposers."""
    _check_context_type(context_type)
    model, field = {
        "QUOTE": (Quote, "quote_number"),
        "POLICY": (Policy, "policy_number"),
        "REQUEST": (PortalRequest, "request_number"),
    }[context_type]
    queryset = model.objects.filter(**{field: ref})
    if proposer_ids is not None:
        queryset = queryset.filter(proposer_id__in=proposer_ids)
    if context_type == "QUOTE":
        queryset = queryset.exclude(status=QuoteStatus.DRAFT.value) if proposer_ids is not None else queryset
    row = queryset.first()
    if row is None:
        raise PortalResourceNotFoundError(f"Não foi encontrado nenhum(a) {context_type.lower()} para esta referência")
    return row


def _item(message: PortalMessage) -> dict:
    return {
        "id": str(message.id),
        "from": "CUSTOMER" if message.sender_type == "CUSTOMER" else "STAFF",
        "fromLabel": "Você" if message.sender_type == "CUSTOMER" else "Q360",
        "body": message.body,
        "createdAt": message.created_at,
    }


# ------------------------------------------------------------- customer
def customer_send(*, account_id: uuid.UUID, context_type: str, context_ref: str, body: str) -> dict:
    body = _clean_body(body)
    row = _resolve(context_type, context_ref, proposer_ids=_scoped_proposer_ids())
    message = PortalMessage.objects.create(
        tenant_id=_tenant_id(), proposer_id=row.proposer_id, context_type=context_type, context_ref=context_ref,
        sender_type="CUSTOMER", sender_ref=str(account_id), body=body, read_by_customer_at=timezone.now(),
    )
    if context_type == "REQUEST":
        requests_service.reopen_on_customer_reply(request=row, account_id=account_id)
    return _item(message)


def customer_thread(*, context_type: str, context_ref: str) -> list[dict]:
    row = _resolve(context_type, context_ref, proposer_ids=_scoped_proposer_ids())
    queryset = PortalMessage.objects.filter(
        proposer_id=row.proposer_id, context_type=context_type, context_ref=context_ref
    )
    with transaction.atomic():
        messages = list(queryset.order_by("created_at"))
        queryset.filter(sender_type="STAFF", read_by_customer_at__isnull=True).update(read_by_customer_at=timezone.now())
    return [_item(m) for m in messages]


def customer_conversations() -> list[dict]:
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return []
    rows = _conversations(PortalMessage.objects.filter(proposer_id__in=proposer_ids), unread_sender="STAFF",
                          unread_field="read_by_customer_at")
    return [{k: v for k, v in row.items() if k != "proposerId"} for row in rows]


def _conversations(queryset, *, unread_sender: str, unread_field: str) -> list[dict]:
    grouped: dict[tuple[str, str], list[PortalMessage]] = defaultdict(list)
    for message in queryset.order_by("created_at"):
        grouped[(message.context_type, message.context_ref)].append(message)
    rows = []
    for (context_type, context_ref), messages in grouped.items():
        last = messages[-1]
        rows.append(
            {
                "contextType": context_type,
                "contextRef": context_ref,
                "proposerId": last.proposer_id,
                "lastMessage": last.body[:140],
                "lastFrom": last.sender_type,
                "lastAt": last.created_at,
                "unread": sum(1 for m in messages if m.sender_type == unread_sender and getattr(m, unread_field) is None),
            }
        )
    rows.sort(key=lambda r: r["lastAt"], reverse=True)
    return rows


# ---------------------------------------------------------------- staff
def staff_send(*, context_type: str, context_ref: str, body: str, actor_ref: str) -> dict:
    body = _clean_body(body)
    row = _resolve(context_type, context_ref, proposer_ids=None)
    with transaction.atomic():
        message = PortalMessage.objects.create(
            tenant_id=_tenant_id(), proposer_id=row.proposer_id, context_type=context_type, context_ref=context_ref,
            sender_type="STAFF", sender_ref=actor_ref, body=body, read_by_staff_at=timezone.now(),
        )
        for account_id in notifications_service.account_ids_for_proposer(row.proposer_id):
            notifications_service.notify_account(
                account_id=account_id, dedupe_key=f"message:{message.id}", code="NEW_MESSAGE",
                title="Nova mensagem da Q360", body=body[:200],
                link=f"/portal/mensagens/{context_type.lower()}/{context_ref}",
            )
    return _item(message)


def staff_thread(*, context_type: str, context_ref: str) -> list[dict]:
    row = _resolve(context_type, context_ref, proposer_ids=None)
    queryset = PortalMessage.objects.filter(
        proposer_id=row.proposer_id, context_type=context_type, context_ref=context_ref
    )
    messages = list(queryset.order_by("created_at"))
    queryset.filter(sender_type="CUSTOMER", read_by_staff_at__isnull=True).update(read_by_staff_at=timezone.now())
    return [_item(m) for m in messages]


def staff_inbox(*, unread_only: bool = False) -> list[dict]:
    rows = _conversations(PortalMessage.objects.all(), unread_sender="CUSTOMER", unread_field="read_by_staff_at")
    holders = dict(Proposer.objects.filter(id__in={r["proposerId"] for r in rows}).values_list("id", "display_name"))
    rows = [{**r, "customerName": holders.get(r["proposerId"])} for r in rows]
    return [r for r in rows if r["unread"] > 0] if unread_only else rows
