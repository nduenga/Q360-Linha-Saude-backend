"""Central de notificações (PDF s.14).

Duas origens, ambas idempotentes por `dedupe_key`:
  - eventos directos (pedido actualizado, mensagem do backoffice) criados por
    quem os provoca via `notify_account`;
  - eventos de estado (cotação aprovada/recusada, apólice emitida, prestação
    em atraso, apólice a vencer, renovação disponível) calculados a partir do
    estado actual por `sync_account` sempre que o cliente abre a central —
    assim não é preciso ligar cada serviço do backoffice ao portal.

Canal: portal. Email/SMS/WhatsApp dependem de integrações que ainda não
existem (PDF: "conforme integrações").
"""
from __future__ import annotations

import datetime
import uuid

from django.utils import timezone

from apps.customer_portal.application import portal_read
from apps.customer_portal.application.self_service import (
    list_my_policies,
    portal_quote_status,
)
from apps.customer_portal.infrastructure.models import CustomerAccountProposer, PortalNotification
from apps.foundation.application.context import CurrentTenantProvider
from apps.policy.infrastructure.models import PremiumInstallment

# An instalment due within this many days raises a "pending payment" notice.
PAYMENT_DUE_SOON_DAYS = 7

_QUOTE_NOTICES = {
    "IN_REVIEW": ("QUOTE_IN_REVIEW", "Cotação {n} em análise", ""),
    "AWAITING_SIGNATURE": ("QUOTE_APPROVED", "Cotação {n} aprovada", "A cotação está aprovada e a aguardar a sua aceitação."),
    # REJECTED não tem corpo fixo: _rejection_body busca o motivo real
    # registado por quem decidiu (QuoteStateHistory.reason_text), em vez de
    # deixar a notificação sem explicação nenhuma.
    "REJECTED": ("QUOTE_REJECTED", "Cotação {n} recusada", None),
    "EXPIRED": ("QUOTE_EXPIRED", "Cotação {n} expirada", "O prazo de validade terminou."),
}


def _rejection_body(quote) -> str:
    history = quote.state_history.filter(to_status="REJECTED").order_by("-changed_at").first()
    reason_text = (history.reason_text or "").strip() if history else ""
    if reason_text:
        return f"Motivo: {reason_text}"
    # reasonCode é sempre preenchido por quem decide, mas é um código técnico
    # (ex. ELIGIBILITY_HARD_STOP) sem tradução para o cliente — mostrar isso
    # cru seria pior do que não mostrar nada. Sem reasonText, só dá para
    # remeter para o apoio ao cliente.
    return "Contacte o apoio ao cliente para saber o motivo."


def _tenant_id():
    return CurrentTenantProvider.require().value


def notify_account(
    *, account_id: uuid.UUID, dedupe_key: str, code: str, title: str, body: str = "", link: str | None = None,
    at: datetime.datetime | None = None,
) -> None:
    PortalNotification.objects.bulk_create(
        [
            PortalNotification(
                tenant_id=_tenant_id(), customer_account_id=account_id, dedupe_key=dedupe_key, code=code,
                title=title, body=body, link=link, created_at=at or timezone.now(),
            )
        ],
        ignore_conflicts=True,
    )


def sync_account(account_id: uuid.UUID, *, today: datetime.date | None = None) -> None:
    today = today or datetime.date.today()
    quotes = list(portal_read.my_visible_quotes())
    policies = list(list_my_policies())

    for quote in quotes:
        status = portal_quote_status(quote, today)
        notice = _QUOTE_NOTICES.get(status)
        if notice is None or quote.quote_number is None:
            continue
        code, title, body = notice
        if status == "REJECTED":
            body = _rejection_body(quote)
        link = f"/portal/cotacoes/{quote.quote_number}"
        at = {"AWAITING_SIGNATURE": quote.approved_at, "REJECTED": quote.rejected_at}.get(status)
        notify_account(
            account_id=account_id, dedupe_key=f"quote:{quote.id}:{status}", code=code,
            title=title.format(n=quote.quote_number), body=body, link=link, at=at,
        )
        if status == "AWAITING_SIGNATURE" and quote.quote_type == "RENEWAL":
            notify_account(
                account_id=account_id, dedupe_key=f"quote:{quote.id}:RENEWAL_AVAILABLE", code="RENEWAL_AVAILABLE",
                title="Proposta de renovação disponível",
                body=f"A cotação {quote.quote_number} é a sua proposta de renovação.", link=link, at=quote.approved_at,
            )

    for policy in policies:
        number = policy.policy_number
        link = f"/portal/apolices/{number}"
        notify_account(
            account_id=account_id, dedupe_key=f"policy:{policy.id}:ISSUED", code="POLICY_ISSUED",
            title=f"Apólice {number} emitida", body="", link=link, at=policy.issued_at,
        )
        if portal_read.policy_phase(policy, today) == "EXPIRING":
            notify_account(
                account_id=account_id, dedupe_key=f"policy:{policy.id}:EXPIRING:{policy.end_date}",
                code="POLICY_EXPIRING", title=f"Apólice {number} a vencer",
                body=f"Termina em {policy.end_date}.", link=f"/portal/renovacoes/{number}",
            )

    policy_numbers = {p.id: p.policy_number for p in policies}
    soon = today + datetime.timedelta(days=PAYMENT_DUE_SOON_DAYS)
    for installment in PremiumInstallment.objects.filter(policy_id__in=list(policy_numbers)).exclude(
        status__in=("PAID", "VOID")
    ):
        number = policy_numbers[installment.policy_id]
        if installment.status == "OVERDUE":
            notify_account(
                account_id=account_id, dedupe_key=f"installment:{installment.id}:OVERDUE", code="PAYMENT_OVERDUE",
                title="Pagamento em atraso", body=f"Apólice {number}: prestação com vencimento em {installment.due_date}.",
                link="/portal/pagamentos",
            )
        elif installment.due_date <= soon:
            notify_account(
                account_id=account_id, dedupe_key=f"installment:{installment.id}:DUE_SOON", code="PAYMENT_PENDING",
                title="Pagamento pendente", body=f"Apólice {number}: prestação vence em {installment.due_date}.",
                link="/portal/pagamentos",
            )


def list_notifications(account_id: uuid.UUID, *, unread_only: bool = False, limit: int = 100) -> dict:
    sync_account(account_id)
    queryset = PortalNotification.objects.filter(customer_account_id=account_id).order_by("-created_at")
    unread = queryset.filter(read_at__isnull=True).count()
    if unread_only:
        queryset = queryset.filter(read_at__isnull=True)
    return {
        "unreadCount": unread,
        "notifications": [
            {
                "id": str(n.id), "code": n.code, "title": n.title, "body": n.body, "link": n.link,
                "createdAt": n.created_at, "read": n.read_at is not None,
            }
            for n in queryset[:limit]
        ],
    }


def mark_read(account_id: uuid.UUID, *, ids: list[uuid.UUID] | None) -> int:
    """`ids=None` marks everything unread as read."""
    queryset = PortalNotification.objects.filter(customer_account_id=account_id, read_at__isnull=True)
    if ids is not None:
        queryset = queryset.filter(id__in=ids)
    return queryset.update(read_at=timezone.now())


def account_ids_for_proposer(proposer_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        CustomerAccountProposer.objects.filter(proposer_id=proposer_id).values_list("customer_account_id", flat=True)
    )

