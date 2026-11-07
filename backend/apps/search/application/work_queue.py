"""Fila «Por tratar»: o trabalho pendente de todos os módulos, numa só lista.

As contagens vêm dos mesmos conjuntos que preenchem a lista, por isso não podem
divergir dela. Cada pessoa só vê as tarefas que as suas permissões lhe deixam
tratar.
"""
from __future__ import annotations

import datetime
from typing import Any

from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.customer_portal.domain import requests as request_rules
from apps.customer_portal.infrastructure.models import PortalRequest
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Permission
from apps.policy.infrastructure.models import Policy, PremiumInstallment
from apps.quote.application.quote_service import SUBMIT_UNDONE_REASON, WITHDRAWN_REASON
from apps.quote.application.review_service import staff_names
from apps.quote.infrastructure.models import Quote, QuoteDiscountApproval, QuoteStateHistory, ReviewTask
from shared.status_labels import status_label

ITEM_LIMIT = 50
RENEWAL_HORIZON_DAYS = 30

REVIEW = "REVIEW"
RETURNED_QUOTE = "RETURNED_QUOTE"
DISCOUNT = "DISCOUNT"
EMISSION = "EMISSION"
FIRST_PREMIUM = "FIRST_PREMIUM"
OVERDUE_INSTALLMENT = "OVERDUE_INSTALLMENT"
CUSTOMER_REQUEST = "CUSTOMER_REQUEST"
RENEWAL = "RENEWAL"

KIND_LABELS = {
    REVIEW: "Revisões",
    RETURNED_QUOTE: "Cotações devolvidas",
    DISCOUNT: "Descontos por decidir",
    EMISSION: "Prontas para emitir",
    FIRST_PREMIUM: "1.ª prestação",
    OVERDUE_INSTALLMENT: "Prestações em atraso",
    CUSTOMER_REQUEST: "Pedidos de clientes",
    RENEWAL: "Renovações",
}


def _item(
    *, kind: str, reference: str | None, entity_id, client: str | None, status: str | None, status_text: str | None,
    due: datetime.date | None, action_code: str, action_label: str, href: str, assigned_to: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind, "kindLabel": KIND_LABELS[kind], "reference": reference, "entityId": str(entity_id), "client": client,
        "status": status, "statusLabel": status_text, "dueDate": due, "assignedTo": assigned_to, "assignedToName": None,
        "detail": detail, "action": {"code": action_code, "label": action_label, "href": href},
    }


# -------------------------------------------------------------- conjuntos
def reviews():
    return ReviewTask.objects.select_related("quote__proposer").filter(status__in=("OPEN", "IN_PROGRESS"))


def returned_quotes():
    latest = QuoteStateHistory.objects.filter(quote_id=OuterRef("pk")).order_by("-changed_at")
    return (
        Quote.objects.select_related("proposer").filter(status="READY")
        .annotate(
            last_from=Subquery(latest.values("from_status")[:1]),
            last_reason=Subquery(latest.values("reason_code")[:1]),
        )
        .filter(last_from="IN_REVIEW").exclude(last_reason__in=(SUBMIT_UNDONE_REASON, WITHDRAWN_REASON))
    )


def discounts():
    return QuoteDiscountApproval.objects.select_related("quote__proposer").filter(status="PENDING")


def emissions():
    return Quote.objects.select_related("proposer").filter(status="APPROVED")


def first_premiums(today: datetime.date):
    return PremiumInstallment.objects.select_related("policy__proposer").filter(
        installment_no=1, status="DUE", due_date__gte=today, policy__status="PENDING_FIRST_PREMIUM"
    )


def overdue_installments(today: datetime.date):
    return PremiumInstallment.objects.select_related("policy__proposer").filter(
        status__in=("DUE", "OVERDUE"), due_date__lt=today, policy__status__in=("ACTIVE", "SUSPENDED")
    )


def customer_requests():
    return PortalRequest.objects.filter(status__in=list(request_rules.OPEN_STATUSES)).exclude(request_type="ACCEPT_QUOTE")


def renewals(today: datetime.date):
    with_open_quote = Quote.objects.filter(quote_type="RENEWAL", source_policy_id__isnull=False).exclude(
        status__in=("CANCELLED", "REJECTED", "EXPIRED")
    ).values("source_policy_id")
    return (
        Policy.objects.select_related("proposer")
        .filter(status="ACTIVE", end_date__range=(today, today + datetime.timedelta(days=RENEWAL_HORIZON_DAYS)))
        .exclude(id__in=with_open_quote)
    )


# -------------------------------------------------------------- linhas
def _review_items(queryset) -> list[dict[str, Any]]:
    return [
        _item(
            kind=REVIEW, reference=t.quote.quote_number, entity_id=t.quote_id, client=t.quote.proposer.display_name,
            status=t.quote.status, status_text=status_label("quote", t.quote.status), due=t.quote.valid_until,
            assigned_to=t.assigned_to, action_code="ASSIGN_TO_ME" if t.assigned_to is None else "DECIDE_REVIEW",
            action_label="Atribuir a mim" if t.assigned_to is None else "Decidir revisão",
            href=f"/subscricao/{t.quote_id}",
        )
        for t in queryset.order_by("created_at")[:ITEM_LIMIT]
    ]


def _returned_items(queryset) -> list[dict[str, Any]]:
    return [
        _item(
            kind=RETURNED_QUOTE, reference=q.quote_number, entity_id=q.id, client=q.proposer.display_name,
            status="RETURNED", status_text=status_label("quote", "RETURNED"), due=q.valid_until,
            action_code="FIX_QUOTE", action_label="Corrigir cotação", href=f"/cotacoes/{q.id}/resumo",
        )
        for q in queryset.order_by("valid_until")[:ITEM_LIMIT]
    ]


def _discount_items(queryset) -> list[dict[str, Any]]:
    return [
        _item(
            kind=DISCOUNT, reference=a.quote.quote_number, entity_id=a.quote_id, client=a.quote.proposer.display_name,
            status=a.status, status_text="A aguardar decisão", due=a.quote.valid_until,
            action_code="DECIDE_DISCOUNT", action_label="Rever desconto", href=f"/cotacoes/{a.quote_id}/resumo",
        )
        for a in queryset.order_by("requested_at")[:ITEM_LIMIT]
    ]


def _emission_items(queryset) -> list[dict[str, Any]]:
    from apps.customer_portal.application.requests_service import accepted_quote_ids

    quotes = list(queryset)
    accepted = accepted_quote_ids(q.id for q in quotes)
    quotes.sort(key=lambda q: (q.id not in accepted, q.valid_until or datetime.date.max))
    return [
        _item(
            kind=EMISSION, reference=q.quote_number, entity_id=q.id, client=q.proposer.display_name,
            status="ACCEPTED" if q.id in accepted else q.status,
            status_text=status_label("quote", "ACCEPTED" if q.id in accepted else q.status), due=q.valid_until,
            detail="Aceite pelo cliente" if q.id in accepted else None,
            action_code="EMIT_POLICY", action_label="Emitir apólice", href=f"/cotacoes/{q.id}/resumo",
        )
        for q in quotes[:ITEM_LIMIT]
    ]


def _installment_items(queryset, *, kind: str, action_code: str, action_label: str, today: datetime.date) -> list[dict[str, Any]]:
    from apps.policy.application.issuance_service import effective_installment_status

    rows = []
    for row in queryset.order_by("due_date")[:ITEM_LIMIT]:
        status = effective_installment_status(row, today)
        rows.append(_item(
            kind=kind, reference=row.policy.policy_number, entity_id=row.policy_id, client=row.policy.proposer.display_name,
            status=status, status_text=status_label("installment", status), due=row.due_date,
            detail=f"Prestação {row.installment_no}", action_code=action_code, action_label=action_label,
            href=f"/cobrancas?policyNumber={row.policy.policy_number}",
        ))
    return rows


def _request_items(queryset) -> list[dict[str, Any]]:
    requests = list(queryset.order_by("created_at")[:ITEM_LIMIT])
    from apps.client.infrastructure.models import Proposer

    holders = dict(Proposer.objects.filter(id__in={r.proposer_id for r in requests}).values_list("id", "display_name"))
    return [
        _item(
            kind=CUSTOMER_REQUEST, reference=r.request_number, entity_id=r.id, client=holders.get(r.proposer_id),
            status=r.status, status_text=status_label("portalRequest", r.status), due=None, detail=r.subject,
            action_code="OPEN_REQUEST", action_label="Abrir pedido", href=f"/atendimento/pedidos/{r.request_number}",
        )
        for r in requests
    ]


def _renewal_items(queryset) -> list[dict[str, Any]]:
    return [
        _item(
            kind=RENEWAL, reference=p.policy_number, entity_id=p.id, client=p.proposer.display_name,
            status=p.status, status_text=status_label("policy", p.status), due=p.end_date,
            action_code="CREATE_RENEWAL", action_label="Criar renovação", href=f"/apolices/{p.id}",
        )
        for p in queryset.order_by("end_date")[:ITEM_LIMIT]
    ]


def build(*, actor: Actor, kind: str | None = None, assignment: str | None = None) -> dict[str, Any]:
    today = timezone.localdate()
    can_review = actor.has_permission(Permission.QUOTE_REVIEW)
    can_approve = actor.has_permission(Permission.QUOTE_APPROVE)
    can_edit = actor.has_permission(Permission.QUOTE_EDIT)
    can_create = actor.has_permission(Permission.QUOTE_CREATE)
    review_rows = reviews()
    if assignment == "mine":
        review_rows = review_rows.filter(assigned_to=actor.actor_id)
    elif assignment == "unassigned":
        review_rows = review_rows.filter(assigned_to__isnull=True)

    sources: list[tuple[str, bool, Any, Any]] = [
        (REVIEW, can_review, review_rows, _review_items),
        (RETURNED_QUOTE, can_edit, returned_quotes(), _returned_items),
        (DISCOUNT, actor.has_permission(Permission.QUOTE_DISCOUNT_APPROVE), discounts(), _discount_items),
        (EMISSION, can_approve, emissions(), _emission_items),
        (FIRST_PREMIUM, can_approve, first_premiums(today), lambda q: _installment_items(
            q, kind=FIRST_PREMIUM, action_code="REGISTER_FIRST_PREMIUM", action_label="Registar 1.ª prestação", today=today)),
        (OVERDUE_INSTALLMENT, can_approve, overdue_installments(today), lambda q: _installment_items(
            q, kind=OVERDUE_INSTALLMENT, action_code="REGISTER_PAYMENT", action_label="Registar pagamento", today=today)),
        (CUSTOMER_REQUEST, can_edit, customer_requests(), _request_items),
        (RENEWAL, can_create, renewals(today), _renewal_items),
    ]
    counts: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    for name, allowed, queryset, render in sources:
        if not allowed:
            continue
        counts[name] = queryset.count()
        if kind in (None, name):
            items.extend(render(queryset))
    items.sort(key=lambda row: (row["dueDate"] is None, row["dueDate"] or datetime.date.max))
    names = staff_names(row["assignedTo"] for row in items)
    for row in items:
        row["assignedToName"] = names.get(row["assignedTo"])
    return {
        "total": sum(counts.values()),
        "dueToday": sum(1 for row in items if row["dueDate"] == today),
        "counts": [{"kind": name, "label": KIND_LABELS[name], "count": count} for name, count in counts.items()],
        "items": items,
    }
