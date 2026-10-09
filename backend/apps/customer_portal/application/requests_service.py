"""Pedidos ao seguro (PDF s.8): o cliente solicita, o backoffice analisa,
aprova, rejeita ou conclui. Toda a resolução do lado do cliente passa pelos
proponentes ligados à conta autenticada (nunca por ids vindos do pedido)."""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from django.db import transaction

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.application import notifications_service
from apps.customer_portal.application.self_service import (
    _scoped_proposer_ids,
    portal_quote_status,
    resolve_my_policy,
)
from apps.customer_portal.domain import requests as rules
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.infrastructure.models import (
    CustomerAccountProposer,
    PortalRequest,
    PortalRequestEvent,
)
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.policy.infrastructure.models import Policy, PolicyMember
from apps.quote.application.numbering_service import next_continuous_value
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote

_audit = AuditService(DjangoAuditRepositoryAdapter())

# A renewal can be requested this many days before the policy ends.
RENEWAL_WINDOW_DAYS = 90
_CANCELLABLE_POLICY_STATUSES = ("ACTIVE", "SUSPENDED", "PENDING_FIRST_PREMIUM")
_MAX_PAYLOAD_KEYS = 20
_INCLUSION_FIELDS = ("firstName", "lastName", "dateOfBirth", "relationship")


def _tenant_id():
    return CurrentTenantProvider.require().value


def _my_quote(quote_number: str) -> Quote:
    proposer_ids = _scoped_proposer_ids()
    quote = (
        Quote.objects.filter(proposer_id__in=proposer_ids, quote_number=quote_number)
        .exclude(status=QuoteStatus.DRAFT.value)
        .select_related("plan__product", "latest_pricing_run")
        .first()
        if proposer_ids
        else None
    )
    if quote is None:
        raise PortalResourceNotFoundError("Não foi encontrada nenhuma cotação com este número (quoteNumber)")
    return quote


def _default_proposer_id() -> uuid.UUID:
    """With no policy/quote to anchor on, the request belongs to the account's
    oldest linked proposer."""
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        raise PortalResourceNotFoundError("A conta de cliente não tem nenhum cliente associado")
    return proposer_ids[0]


def _validate_payload(request_type: str, payload: Any, policy: Policy | None) -> dict:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict) or len(payload) > _MAX_PAYLOAD_KEYS:
        raise rules.PortalRequestInvalidError(f"O conteúdo (payload) tem de ser um objeto com no máximo {_MAX_PAYLOAD_KEYS} campos")
    if request_type == "MEMBER_INCLUSION":
        missing = [f for f in _INCLUSION_FIELDS if not str(payload.get(f) or "").strip()]
        if missing:
            raise rules.PortalRequestInvalidError(f"Faltam campos no conteúdo (payload): {', '.join(missing)}")
        try:
            datetime.date.fromisoformat(str(payload["dateOfBirth"]))
        except ValueError as exc:
            raise rules.PortalRequestInvalidError("A data de nascimento (payload.dateOfBirth) tem de estar no formato AAAA-MM-DD") from exc
    if request_type == "MEMBER_EXCLUSION":
        try:
            member_id = uuid.UUID(str(payload.get("memberId")))
        except ValueError as exc:
            raise rules.PortalRequestInvalidError("A pessoa segura (payload.memberId) é obrigatória") from exc
        if policy is None or not PolicyMember.objects.filter(
            policy=policy, member_id=member_id, status__in=("ACTIVE", "PENDING")
        ).exists():
            raise rules.PortalRequestInvalidError("A pessoa segura indicada (payload.memberId) não pertence a esta apólice")
    return payload


def create_request(
    *,
    account_id: uuid.UUID,
    request_type: str,
    subject: str,
    description: str,
    policy_number: str | None,
    quote_number: str | None,
    payload: Any,
    today: datetime.date | None = None,
) -> PortalRequest:
    spec = rules.REQUEST_TYPES.get(request_type)
    if spec is None:
        raise rules.PortalRequestInvalidError(f"O tipo de pedido (requestType) tem de ser um de {sorted(rules.REQUEST_TYPES)}")
    today = today or datetime.date.today()

    policy = resolve_my_policy(policy_number) if policy_number else None
    quote = _my_quote(quote_number) if quote_number else None
    if spec["policy"] and policy is None:
        raise rules.PortalRequestInvalidError("O número da apólice (policyNumber) é obrigatório para este tipo de pedido")
    if spec["quote"] and quote is None:
        raise rules.PortalRequestInvalidError("O número da cotação (quoteNumber) é obrigatório para este tipo de pedido")

    if request_type == "RENEWAL":
        days_left = (policy.end_date - today).days if policy.end_date else None
        if policy.status != "ACTIVE" or days_left is None or days_left > RENEWAL_WINDOW_DAYS or days_left < 0:
            raise rules.PortalRequestInvalidError(
                f"A renovação só pode ser pedida para uma apólice ativa que termine dentro de {RENEWAL_WINDOW_DAYS} dias"
            )
    if request_type == "CANCELLATION" and policy.status not in _CANCELLABLE_POLICY_STATUSES:
        raise rules.PortalRequestInvalidError("Esta apólice não pode ser cancelada no estado em que se encontra")
    if request_type == "ACCEPT_QUOTE" and portal_quote_status(quote, today) != "AWAITING_SIGNATURE":
        raise rules.PortalRequestInvalidError("Só é possível aceitar uma cotação aprovada e ainda dentro da validade")

    payload = _validate_payload(request_type, payload, policy)

    if spec["single"]:
        clash = PortalRequest.objects.filter(
            request_type=request_type, status__in=list(rules.OPEN_STATUSES),
            policy_id=policy.id if policy else None, quote_id=quote.id if quote else None,
        ).exists()
        if clash:
            raise rules.PortalRequestConflictError("Já existe um pedido em aberto deste tipo para este destino")

    proposer_id = policy.proposer_id if policy else quote.proposer_id if quote else _default_proposer_id()
    with transaction.atomic():
        request = PortalRequest.objects.create(
            tenant_id=_tenant_id(),
            request_number=next_continuous_value(sequence_code="PORTAL_REQUEST", prefix="PED-"),
            customer_account_id=account_id,
            proposer_id=proposer_id,
            policy_id=policy.id if policy else None,
            quote_id=quote.id if quote else None,
            request_type=request_type,
            subject=(subject or "").strip() or spec["label"],
            description=(description or "").strip(),
            payload_json=payload,
            status=rules.OPEN,
        )
        PortalRequestEvent.objects.create(
            tenant_id=_tenant_id(), request=request, from_status=None, to_status=rules.OPEN,
            note=None, actor_type="CUSTOMER", actor_ref=str(account_id),
        )
    _audit.record(
        action="customer_portal.request_created", entity_type="PortalRequest", entity_id=str(request.id),
        metadata={"type": request_type, "number": request.request_number},
    )
    return request


def _item(request: PortalRequest, *, policy_number: str | None, quote_number: str | None) -> dict:
    return {
        "requestNumber": request.request_number,
        "type": request.request_type,
        "typeLabel": rules.REQUEST_TYPES[request.request_type]["label"],
        "subject": request.subject,
        "description": request.description,
        "status": request.status,
        "statusLabel": rules.STATUS_LABELS[request.status],
        "policyNumber": policy_number,
        "quoteNumber": quote_number,
        "resolutionNote": request.resolution_note,
        "createdAt": request.created_at,
        "updatedAt": request.updated_at,
    }


def _numbers(requests: list[PortalRequest]) -> tuple[dict, dict]:
    policies = dict(
        Policy.objects.filter(id__in=[r.policy_id for r in requests if r.policy_id]).values_list("id", "policy_number")
    )
    quotes = dict(
        Quote.objects.filter(id__in=[r.quote_id for r in requests if r.quote_id]).values_list("id", "quote_number")
    )
    return policies, quotes


def items_for(requests: list[PortalRequest]) -> list[dict]:
    policies, quotes = _numbers(requests)
    return [_item(r, policy_number=policies.get(r.policy_id), quote_number=quotes.get(r.quote_id)) for r in requests]


def list_my_requests(*, status: str | None = None) -> list[dict]:
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return []
    queryset = PortalRequest.objects.filter(proposer_id__in=proposer_ids).order_by("-created_at")
    if status:
        queryset = queryset.filter(status=status)
    return items_for(list(queryset))


def _my_request(request_number: str) -> PortalRequest:
    proposer_ids = _scoped_proposer_ids()
    request = (
        PortalRequest.objects.filter(proposer_id__in=proposer_ids, request_number=request_number).first()
        if proposer_ids
        else None
    )
    if request is None:
        raise PortalResourceNotFoundError("Não foi encontrado nenhum pedido com este número (requestNumber)")
    return request


def _events(request: PortalRequest) -> list[dict]:
    return [
        {
            "status": e.to_status, "statusLabel": rules.STATUS_LABELS[e.to_status],
            "note": e.note, "by": "Você" if e.actor_type == "CUSTOMER" else "Q360", "at": e.created_at,
        }
        for e in PortalRequestEvent.objects.filter(request=request).order_by("created_at")
    ]


def get_my_request(request_number: str) -> dict:
    request = _my_request(request_number)
    return {**items_for([request])[0], "history": _events(request)}


# ---------------------------------------------------------------- staff
def staff_list(*, status: str | None = None, request_type: str | None = None) -> list[dict]:
    queryset = PortalRequest.objects.order_by("created_at")
    if status:
        queryset = queryset.filter(status=status)
    if request_type:
        queryset = queryset.filter(request_type=request_type)
    requests = list(queryset)
    holders = dict(Proposer.objects.filter(id__in=[r.proposer_id for r in requests]).values_list("id", "display_name"))
    return [{**item, "customerName": holders.get(r.proposer_id), "payload": r.payload_json}
            for item, r in zip(items_for(requests), requests)]


def staff_get(request_number: str) -> dict:
    request = PortalRequest.objects.filter(request_number=request_number).first()
    if request is None:
        raise PortalResourceNotFoundError("Não foi encontrado nenhum pedido com este número (requestNumber)")
    holder = Proposer.objects.filter(id=request.proposer_id).first()
    return {
        **items_for([request])[0],
        "customerName": holder.display_name if holder else None,
        "payload": request.payload_json,
        "history": _events(request),
    }


def staff_transition(*, request_number: str, to_status: str, note: str | None, actor_ref: str) -> dict:
    request = PortalRequest.objects.filter(request_number=request_number).first()
    if request is None:
        raise PortalResourceNotFoundError("Não foi encontrado nenhum pedido com este número (requestNumber)")
    rules.assert_transition(request.status, to_status, note)
    previous = request.status
    resolution_note = request.resolution_note
    if to_status in (rules.APPROVED, rules.REJECTED, rules.COMPLETED) and (note or "").strip():
        resolution_note = note.strip()
    with transaction.atomic():
        updated = PortalRequest.objects.filter(id=request.id, status=previous).update(
            status=to_status,
            resolution_note=resolution_note,
            row_version=request.row_version + 1,
        )
        if updated == 0:
            raise rules.PortalRequestConflictError("O pedido foi alterado entretanto; recarregue e tente de novo")
        PortalRequestEvent.objects.create(
            tenant_id=_tenant_id(), request=request, from_status=previous, to_status=to_status,
            note=(note or "").strip() or None, actor_type="STAFF", actor_ref=actor_ref,
        )
        notifications_service.notify_account(
            account_id=request.customer_account_id,
            dedupe_key=f"request:{request.id}:{to_status}",
            code="REQUEST_UPDATED",
            title=f"Pedido {request.request_number}: {rules.STATUS_LABELS[to_status]}",
            body=(note or "").strip(),
            link=f"/portal/pedidos/{request.request_number}",
        )
    _audit.record(
        action="customer_portal.request_transitioned", entity_type="PortalRequest", entity_id=str(request.id),
        metadata={"from": previous, "to": to_status, "actor": actor_ref},
    )
    request.refresh_from_db()
    return staff_get(request_number)


def reopen_on_customer_reply(*, request: PortalRequest, account_id: uuid.UUID) -> None:
    """A customer answer to «A aguardar o cliente» puts the request back in analysis."""
    if request.status != rules.AWAITING_CUSTOMER:
        return
    PortalRequest.objects.filter(id=request.id, status=rules.AWAITING_CUSTOMER).update(
        status=rules.IN_REVIEW, row_version=request.row_version + 1
    )
    PortalRequestEvent.objects.create(
        tenant_id=_tenant_id(), request=request, from_status=rules.AWAITING_CUSTOMER, to_status=rules.IN_REVIEW,
        note="Resposta do cliente", actor_type="CUSTOMER", actor_ref=str(account_id),
    )


def linked_account_ids(proposer_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        CustomerAccountProposer.objects.filter(proposer_id=proposer_id).values_list("customer_account_id", flat=True)
    )



def complete_accept_requests_for_quote(*, quote_id: uuid.UUID, policy_number: str | None) -> int:
    """A apólice foi emitida a partir desta cotação: os pedidos de aceitação
    (`ACCEPT_QUOTE`) ainda em aberto ficam concluídos e o cliente é avisado.
    É o fecho do circuito — o GTE não tem de os tratar à mão."""
    note = f"Apólice {policy_number} emitida." if policy_number else "Apólice emitida."
    done = 0
    for request in PortalRequest.objects.filter(
        quote_id=quote_id, request_type="ACCEPT_QUOTE", status__in=list(rules.OPEN_STATUSES)
    ):
        previous = request.status
        updated = PortalRequest.objects.filter(id=request.id, status=previous).update(
            status=rules.COMPLETED, resolution_note=note, row_version=request.row_version + 1
        )
        if updated == 0:
            continue
        PortalRequestEvent.objects.create(
            tenant_id=_tenant_id(), request=request, from_status=previous, to_status=rules.COMPLETED,
            note=note, actor_type="STAFF", actor_ref="system:policy-issued",
        )
        notifications_service.notify_account(
            account_id=request.customer_account_id,
            dedupe_key=f"request:{request.id}:{rules.COMPLETED}",
            code="REQUEST_UPDATED",
            title=f"Pedido {request.request_number}: {rules.STATUS_LABELS[rules.COMPLETED]}",
            body=note,
            link=f"/portal/pedidos/{request.request_number}",
        )
        done += 1
    return done
