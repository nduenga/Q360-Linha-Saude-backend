"""Read-only customer-facing views for the Portal Cliente (Portal_Cliente_Sistema_
Cotacoes_Saude.pdf, MVP): dashboard, quote detail + timeline, policy detail,
beneficiaries, payments, documents, profile and the digital card.

Same rule as `self_service.py`: everything is resolved from the proposers
linked to the authenticated account (`require_customer_proposer_ids`), never
from an id supplied by the request, and only customer-facing fields leave this
module — no pricing rules, underwriting notes, loadings or internal reasons
(PDF section 19).
"""
from __future__ import annotations

from shared import formatting as fmt

import datetime
import uuid
from collections import defaultdict
from decimal import Decimal

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.customer_portal.application.self_service import (
    list_my_policies,
    portal_quote_item,
    portal_quote_status,
    resolve_my_policy,
    _scoped_proposer_ids,
)
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.policy.infrastructure.models import (
    Policy,
    PolicyMember,
    PolicySignature,
    PolicyStateHistory,
    PremiumInstallment,
)
from apps.pricing.domain.money import round_amount
from apps.client.domain.member_documents import requirement_for_reason
from apps.policy.application import issuance_service, policy_document
from apps.quote.application import proposal_service
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Document, Quote

# A policy ending within this many days is shown as "A vencer".
EXPIRING_SOON_DAYS = 60
# An approved quote ending within this many days raises an alert.
QUOTE_EXPIRING_SOON_DAYS = 7

POLICY_STATUS_LABELS = {
    "PENDING_FIRST_PREMIUM": "A aguardar 1.º pagamento",
    "ACTIVE": "Activa",
    "SUSPENDED": "Suspensa",
    "TERMINATED": "Terminada",
    "CANCELLED": "Cancelada",
    "EXPIRED": "Expirada",
    "RENEWED": "Renovada",
}


def _money(value) -> str:
    return str(round_amount(Decimal(value)))


def _today(today: datetime.date | None) -> datetime.date:
    return today or datetime.date.today()


def policy_phase(policy: Policy, today: datetime.date) -> str:
    """Customer-facing bucket used by the dashboard and the "Minhas Apólices" menu."""
    if policy.status == "ACTIVE":
        if policy.end_date is not None and policy.end_date <= today + datetime.timedelta(days=EXPIRING_SOON_DAYS):
            return "EXPIRING"
        return "ACTIVE"
    return {"RENEWED": "RENEWED", "EXPIRED": "EXPIRED", "CANCELLED": "CANCELLED"}.get(policy.status, "OTHER")


def my_visible_quotes(*, include_drafts: bool = False):
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return Quote.objects.none()
    queryset = Quote.objects.filter(proposer_id__in=proposer_ids)
    if not include_drafts:
        queryset = queryset.exclude(status=QuoteStatus.DRAFT.value)
    return queryset.select_related("plan__product", "latest_pricing_run")


def _member_name(member: InsuredMember) -> str:
    return " ".join(part for part in (member.first_name, member.last_name) if part) or "Beneficiário"


def _installment_item(installment: PremiumInstallment, policy_number: str | None) -> dict:
    return {
        "id": str(installment.id),
        "policyNumber": policy_number,
        "installmentNo": installment.installment_no,
        "periodFrom": installment.period_from,
        "periodTo": installment.period_to,
        "dueDate": installment.due_date,
        "amount": _money(installment.amount),
        "currencyCode": installment.currency_code,
        "status": issuance_service.effective_installment_status(installment),
        "paidAt": installment.paid_at,
    }


# ---------------------------------------------------------------- quotes
def get_my_quote(quote_number: str, *, today: datetime.date | None = None) -> dict:
    """Quote detail with the journey timeline (PDF sections 4 and 17). Only
    events the system actually records are listed; a stage the platform does
    not track (questionnaire, document upload) is not invented."""
    today = _today(today)
    quote = my_visible_quotes().filter(quote_number=quote_number).first()
    if quote is None:
        raise PortalResourceNotFoundError("Não foi encontrada nenhuma cotação com este número (quoteNumber)")

    policy = Policy.objects.filter(source_quote_id=quote.id).first()
    item = portal_quote_item(quote, policy_number=policy.policy_number if policy else None, today=today)

    events: list[dict] = [{"code": "QUOTE_CREATED", "label": "Simulação criada", "at": quote.created_at}]
    if quote.submitted_at:
        events.append({"code": "SUBMITTED", "label": "Proposta submetida", "at": quote.submitted_at})
    if quote.approved_at:
        events.append({"code": "APPROVED", "label": "Proposta aprovada", "at": quote.approved_at})
    if quote.rejected_at:
        events.append({"code": "REJECTED", "label": "Proposta recusada", "at": quote.rejected_at})
    for document in Document.objects.filter(quote=quote, status="GENERATED").order_by("generated_at"):
        if document.generated_at:
            events.append({"code": "PROPOSAL_AVAILABLE", "label": "Proposta disponível", "at": document.generated_at})
    if policy is not None:
        signature = PolicySignature.objects.filter(policy=policy).first()
        if signature is not None:
            events.append({"code": "ACCEPTED", "label": "Proposta aceite", "at": signature.signed_at})
        events.append({"code": "POLICY_ISSUED", "label": "Apólice emitida", "at": policy.issued_at})
        first_paid = (
            PremiumInstallment.objects.filter(policy=policy, paid_at__isnull=False).order_by("paid_at").first()
        )
        if first_paid is not None:
            events.append({"code": "PAYMENT_REGISTERED", "label": "Pagamento registado", "at": first_paid.paid_at})
    events.sort(key=lambda event: event["at"])

    item["timeline"] = events
    item["currentStage"] = item["status"]
    return item


# -------------------------------------------------------------- policies
def get_my_policy(policy_number: str, *, today: datetime.date | None = None) -> dict:
    """Policy detail (PDF section 5): terms, premium, holder, insured people,
    instalments. Coverages are served by `/plan-benefits`."""
    today = _today(today)
    policy = resolve_my_policy(policy_number)
    proposer = Proposer.objects.filter(id=policy.proposer_id).first()
    plan = policy.plan
    installments = list(PremiumInstallment.objects.filter(policy=policy).exclude(status="VOID").order_by("installment_no"))
    total = sum((i.amount for i in installments), Decimal("0"))
    members = _policy_members(policy)
    signature = PolicySignature.objects.filter(policy=policy).first()

    return {
        "policyNumber": policy.policy_number,
        "status": policy.status,
        "statusLabel": POLICY_STATUS_LABELS.get(policy.status, policy.status),
        "phase": policy_phase(policy, today),
        "policyType": policy.policy_type,
        "product": {"name": plan.product.name} if plan.product else None,
        "plan": {"name": plan.name},
        "startDate": policy.start_date,
        "endDate": policy.end_date,
        "termMonths": policy.term_months,
        "paymentFrequency": policy.payment_frequency,
        "currencyCode": policy.currency_code,
        "totalPremium": _money(total) if installments else None,
        "holder": {
            "name": proposer.display_name if proposer else None,
            "type": proposer.proposer_type if proposer else None,
        },
        "signedAt": signature.signed_at if signature else None,
        "members": members,
        "installments": [_installment_item(i, policy.policy_number) for i in installments],
    }


def _policy_members(policy: Policy) -> list[dict]:
    rows = list(
        PolicyMember.objects
        .filter(policy=policy)
        .select_related("member")
        .order_by("created_at")
    )

    result = []

    for row in rows:
        member = row.member

        if member is None:
            continue

        result.append(
            {
                "memberId": str(member.id),

                "name": _member_name(member),

                "relationship": member.relationship_code,

                "dateOfBirth": member.date_of_birth,

                # Estado do vínculo na apólice.
                "status": row.status,

                # Estado global do beneficiário.
                "beneficiaryStatus": member.status,

                # Data em que foi incluído.
                "inclusionDate": row.inclusion_date,

                # Data em que foi excluído.
                "exclusionDate": row.exclusion_date,

                # Pendência: o que falta enviar para esta pessoa ficar coberta
                # (envio em POST /customer-portal/members/{memberId}/documents).
                "pendingReasonCode": row.pending_reason_code,
                "requiredDocument": requirement_for_reason(row.pending_reason_code),
            }
        )

    return result


def list_my_policies_summary(*, today: datetime.date | None = None, phase: str | None = None) -> list[dict]:
    """Menu "Minhas Apólices" (Ativas / A vencer / Renovadas / Expiradas /
    Canceladas) — the same list as `/me`, filterable by phase."""
    today = _today(today)
    items = []
    for policy in list_my_policies().select_related("plan__product"):
        current_phase = policy_phase(policy, today)
        if phase and current_phase != phase:
            continue
        items.append(
            {
                "policyNumber": policy.policy_number,
                "status": policy.status,
                "statusLabel": POLICY_STATUS_LABELS.get(policy.status, policy.status),
                "phase": current_phase,
                "product": {"name": policy.plan.product.name} if policy.plan.product else None,
                "plan": {"name": policy.plan.name},
                "startDate": policy.start_date,
                "endDate": policy.end_date,
            }
        )
    return items


# --------------------------------------------------------- beneficiaries
def list_my_beneficiaries() -> list[dict]:
    """People covered under the caller's policies (PDF section 7, read part)."""
    items = []
    for policy in list_my_policies().select_related("plan"):
        for member in _policy_members(policy):
            items.append({**member, "policyNumber": policy.policy_number, "plan": {"name": policy.plan.name}})
    return items


# -------------------------------------------------------------- payments
def list_my_payments(*, status: str | None = None) -> dict:
    """Financial area (PDF section 10): every instalment, plus totals per
    currency. Paid / pending (DUE) / overdue are the instalment statuses."""
    policies = {p.id: p for p in list_my_policies()}
    if not policies:
        return {"installments": [], "totals": []}
    queryset = PremiumInstallment.objects.filter(policy_id__in=list(policies)).exclude(status="VOID")
    installments = list(queryset.order_by("due_date"))
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"paid": Decimal("0"), "pending": Decimal("0"), "overdue": Decimal("0")})
    for installment in installments:
        bucket = {"PAID": "paid", "DUE": "pending", "OVERDUE": "overdue"}.get(
            issuance_service.effective_installment_status(installment)
        )
        if bucket:
            totals[installment.currency_code][bucket] += installment.amount
    items = [
        _installment_item(i, policies[i.policy_id].policy_number)
        for i in installments
        if status is None or issuance_service.effective_installment_status(i) == status
    ]
    return {
        "installments": items,
        "totals": [
            {"currencyCode": code, **{key: _money(value) for key, value in buckets.items()}}
            for code, buckets in sorted(totals.items())
        ],
    }


# ------------------------------------------------------------- documents
def list_my_documents() -> list[dict]:
    """Document centre (PDF section 9): quote proposals and the digital policy
    of each issued policy. Statements and receipts are generated on request
    (`/policies/{number}/statement`)."""
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return []
    documents = list(
        Document.objects.filter(
            quote__proposer_id__in=proposer_ids, status="GENERATED", file_name__isnull=False
        )
        .exclude(quote__status=QuoteStatus.DRAFT.value)
        .select_related("quote")
        .order_by("-generated_at")
    )
    return [
        {
            "id": str(d.id),
            "type": "PROPOSTA",
            "title": f"Proposta {d.quote.quote_number or ''}".strip(),
            "quoteNumber": d.quote.quote_number,
            "policyNumber": None,
            "format": d.format,
            "fileName": d.file_name,
            "generatedAt": d.generated_at,
        }
        for d in documents
    ] + _policy_document_items()


def _policy_document_items() -> list[dict]:
    """A apólice digital de cada apólice emitida (o `id` é o da apólice)."""
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return []
    policies = Policy.objects.filter(proposer_id__in=proposer_ids).order_by("-issued_at")
    return [
        {
            "id": str(p.id),
            "type": "APOLICE",
            "title": f"Apólice {p.policy_number}",
            "quoteNumber": None,
            "policyNumber": p.policy_number,
            "format": "PDF",
            "fileName": f"apolice-{p.policy_number}.pdf",
            "generatedAt": p.issued_at,
        }
        for p in policies
    ]


def open_my_document(document_id: uuid.UUID) -> tuple[bytes, str, str | None]:
    proposer_ids = _scoped_proposer_ids()
    document = (
        Document.objects.filter(id=document_id, quote__proposer_id__in=proposer_ids, status="GENERATED")
        .exclude(quote__status=QuoteStatus.DRAFT.value)
        .first()
        if proposer_ids
        else None
    )
    if document is None:
        policy = Policy.objects.filter(id=document_id, proposer_id__in=proposer_ids).first() if proposer_ids else None
        if policy is None:
            raise PortalResourceNotFoundError("Documento não encontrado")
        return policy_document.policy_document(policy, "PDF")
    return proposal_service.read_file(document), document.content_type or "application/octet-stream", document.file_name


# --------------------------------------------------------------- profile
def get_my_profile(*, account_email: str | None = None) -> dict:
    """Customer profile (PDF section 13, read part). Login is by one-time code,
    so there is no password / 2FA to manage."""
    proposer_ids = _scoped_proposer_ids()
    proposers = Proposer.objects.filter(id__in=proposer_ids).order_by("created_at") if proposer_ids else []
    return {
        "accountEmail": account_email,
        "proposers": [
            {
                "name": p.display_name,
                "type": p.proposer_type,
                "nif": p.nif,
                "registrationNumber": p.registration_number,
                "email": p.email,
                "phone": p.phone,
                "address": p.address,
                "province": p.province,
                "municipality": p.municipality,
            }
            for p in proposers
        ],
    }


# ---------------------------------------------------------- digital card
def get_my_card(policy_number: str, member_id: uuid.UUID, *, today: datetime.date | None = None) -> dict:
    """Digital card (PDF section 16). The QR code needs a provider integration
    (phase 3), so it is not part of the payload."""
    policy = resolve_my_policy(policy_number)
    row = PolicyMember.objects.filter(policy=policy, member_id=member_id).first()
    member = InsuredMember.objects.filter(id=member_id).first() if row else None
    if row is None or member is None:
        raise PortalResourceNotFoundError("Esta pessoa segura não pertence a esta apólice")
    return {
        "memberName": _member_name(member),
        "memberNumber": str(member.id).split("-")[0].upper(),
        "relationship": member.relationship_code,
        "policyNumber": policy.policy_number,
        "plan": {"name": policy.plan.name},
        "product": {"name": policy.plan.product.name} if policy.plan.product else None,
        "validFrom": policy.start_date,
        "validUntil": policy.end_date,
        "policyStatus": policy.status,
        "memberStatus": row.status,
    }


# ------------------------------------------------------------- dashboard
def get_my_dashboard(*, today: datetime.date | None = None) -> dict:
    """Actionable summary (PDF section 2)."""
    today = _today(today)
    quotes = list(my_visible_quotes())
    quote_counts: dict[str, int] = defaultdict(int)
    for quote in quotes:
        quote_counts[portal_quote_status(quote, today)] += 1

    policies = list(list_my_policies().select_related("plan__product"))
    policy_counts: dict[str, int] = defaultdict(int)
    for policy in policies:
        policy_counts[policy_phase(policy, today)] += 1

    payments = list_my_payments()
    open_installments = [i for i in payments["installments"] if i["status"] in ("DUE", "OVERDUE")]

    upcoming: list[dict] = []
    alerts: list[dict] = []
    for installment in open_installments[:5]:
        upcoming.append({"type": "PAYMENT", "date": installment["dueDate"], "policyNumber": installment["policyNumber"],
                         "amount": installment["amount"], "currencyCode": installment["currencyCode"]})
    for installment in open_installments:
        if installment["status"] == "OVERDUE":
            alerts.append({"code": "PAYMENT_OVERDUE", "severity": "danger", "policyNumber": installment["policyNumber"],
                           "message": f"Prestação de {fmt.money(installment['amount'], installment['currencyCode'])} em atraso."})
    for policy in policies:
        phase = policy_phase(policy, today)
        if phase == "EXPIRING":
            upcoming.append({"type": "POLICY_EXPIRY", "date": policy.end_date, "policyNumber": policy.policy_number})
            alerts.append({"code": "POLICY_EXPIRING", "severity": "warning", "policyNumber": policy.policy_number,
                           "message": f"A apólice {policy.policy_number} termina em {policy.end_date}."})
        if policy.status == "PENDING_FIRST_PREMIUM":
            alerts.append({"code": "FIRST_PREMIUM_PENDING", "severity": "warning", "policyNumber": policy.policy_number,
                           "message": f"A apólice {policy.policy_number} aguarda o pagamento do 1.º prémio."})
        if policy.status == "SUSPENDED":
            alerts.append({"code": "POLICY_SUSPENDED", "severity": "danger", "policyNumber": policy.policy_number,
                           "message": f"A apólice {policy.policy_number} está suspensa."})
    for quote in quotes:
        if portal_quote_status(quote, today) == "AWAITING_SIGNATURE" and quote.valid_until is not None:
            if quote.valid_until <= today + datetime.timedelta(days=QUOTE_EXPIRING_SOON_DAYS):
                alerts.append({"code": "QUOTE_EXPIRING", "severity": "warning", "quoteNumber": quote.quote_number,
                               "message": f"A cotação {quote.quote_number} é válida até {quote.valid_until}."})
    upcoming.sort(key=lambda event: event["date"])

    return {
        "quotes": {"total": len(quotes), "byStatus": dict(quote_counts)},
        "policies": {"total": len(policies), "byPhase": dict(policy_counts)},
        "upcoming": upcoming,
        "alerts": alerts,
        "financial": payments["totals"],
    }


def list_my_state_history(policy_number: str) -> list[dict]:
    """Policy-level activity (PDF section 17) — state changes only; internal
    reason texts are never returned."""
    policy = resolve_my_policy(policy_number)
    return [
        {"fromStatus": h.from_status, "toStatus": h.to_status, "at": h.changed_at}
        for h in PolicyStateHistory.objects.filter(policy=policy).order_by("changed_at")
    ]


def my_policy_document(policy_number: str, fmt: str = "PDF") -> tuple[bytes, str, str]:
    return policy_document.policy_document(resolve_my_policy(policy_number), fmt)


def my_policy_statement(policy_number: str, *, kind: str, installment_no: int | None) -> tuple[bytes, str, str]:
    return policy_document.statement_document(resolve_my_policy(policy_number), kind=kind, installment_no=installment_no)
