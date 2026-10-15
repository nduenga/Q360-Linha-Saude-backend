"""Emissão da apólice num só passo, a partir da plataforma.

Fluxo do GTE: a cotação está APROVADA → o cliente assina presencialmente →
o GTE abre o rascunho (`build_draft`, tudo pré-preenchido com os dados da
cotação), confirma assinatura e pagamento e emite (`emit_policy`). Por baixo
usa as mesmas regras de `issuance_service` (assinatura → apólice; 1.ª prestação
→ apólice em vigor); aqui só se juntam num passo, atómico: ou fica tudo, ou nada.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.policy.application import issuance_service, policy_document
from apps.policy.infrastructure.models import Policy
from apps.quote.application import proposal_content
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote

DEFAULT_TERM_MONTHS = 12
DEFAULT_FREQUENCY = "ANUAL"
PAYMENT_METHODS = [
    {"code": "NUMERARIO", "label": "Numerário"},
    {"code": "TRANSFERENCIA", "label": "Transferência bancária"},
    {"code": "MULTICAIXA", "label": "Multicaixa"},
    {"code": "TPA", "label": "TPA"},
]


def _blocking_reason(quote: Quote) -> str | None:
    if Policy.objects.filter(source_quote=quote).exists():
        return "Esta cotação já originou uma apólice."
    if quote.status != QuoteStatus.APPROVED.value:
        return f"A cotação está em {quote.status}; só uma cotação APROVADA pode virar apólice."
    if quote.latest_pricing_run is None or quote.latest_pricing_run.total_amount is None:
        return "A cotação não tem prémio calculado."
    return None


def _installment_preview(quote: Quote, total: Decimal | None, currency: str) -> dict[str, list[dict[str, str]]]:
    if total is None:
        return {}
    preview = {}
    for frequency, count in issuance_service._INSTALLMENT_COUNT.items():
        amount = issuance_service.installment_amount(quote, total, frequency)
        preview[frequency] = [{"installmentNo": n, "amount": str(amount), "currencyCode": currency} for n in range(1, count + 1)]
    return preview


def build_draft(quote: Quote) -> dict[str, Any]:
    """Tudo o que a apólice precisa, vindo da cotação. O GTE só acrescenta o
    que não existe na cotação: assinatura, data de assinatura e pagamento."""
    reason = _blocking_reason(quote)
    existing = Policy.objects.filter(source_quote=quote).first()
    run = quote.latest_pricing_run
    currency = quote.currency_code or (run.currency_code if run else None) or "AOA"
    total = run.total_amount if run and run.total_amount is not None else None
    proposer = quote.proposer

    draft: dict[str, Any] = {
        "quoteId": str(quote.id),
        "quoteNumber": quote.quote_number,
        "quoteStatus": quote.status,
        "rowVersion": quote.row_version,
        "canEmit": reason is None,
        "blockingReason": reason,
        # A validade só trava na emissão, face à data de assinatura (issue_policy); aqui só se avisa.
        "warnings": (
            [f"A cotação é válida até {quote.valid_until}; a assinatura tem de ser até essa data."]
            if quote.valid_until is not None and quote.valid_until < timezone.now().date()
            else []
        ),
        "policyId": str(existing.id) if existing else None,
        "policyNumber": existing.policy_number if existing else None,
        "holder": {
            "id": str(proposer.id), "name": proposer.display_name, "type": proposer.proposer_type,
            "document": proposer.nif or proposer.registration_number, "email": proposer.email, "phone": proposer.phone,
        },
        "plan": {"product": quote.plan.product.name if quote.plan.product else None, "name": quote.plan.name},
        "currencyCode": currency,
        "effectiveDate": quote.effective_date,
        "validUntil": quote.valid_until,
        "premium": {"total": str(issuance_service._round2(total)) if total is not None else None, "currencyCode": currency},
        "defaults": {
            "termMonths": DEFAULT_TERM_MONTHS,
            "paymentFrequency": DEFAULT_FREQUENCY,
            "requestedStartDate": None,
            "signedAt": timezone.now(),
            "signatureMethod": "PRESENCIAL",
            "signatory": {
                "name": proposer.display_name,
                "documentType": "BI",
                "documentNumber": proposer.nif or proposer.registration_number or "",
                "capacity": "REPRESENTANTE_LEGAL" if proposer.proposer_type == "ORGANISATION" else "TOMADOR",
            },
        },
        "installmentsPreview": _installment_preview(quote, total, currency),
        "paymentMethods": PAYMENT_METHODS,
        "members": [],
        "terms": None,
    }

    for quote_member in quote.members.select_related("member", "eligibility_evaluation").order_by("created_at", "id"):
        evaluation = quote_member.eligibility_evaluation
        decision = evaluation.decision if evaluation else None
        member_status = issuance_service._ELIGIBILITY_TO_POLICY_MEMBER_STATUS.get(decision)
        draft["members"].append(
            {
                "memberId": str(quote_member.member_id),
                "name": proposal_content._member_name(quote_member.member),
                "eligibilityDecision": decision,
                "policyStatus": member_status or "EXCLUDED",
            }
        )

    if run is not None:
        from apps.pricing.interfaces.serializers import render_preview

        content = proposal_content.build_content(
            quote=quote, scenario=None, calculation=render_preview(run), generated_on=timezone.now().date()
        )
        contracted = [c for c in content["coverages"] if c["contracted"]]
        draft["terms"] = {
            "segment": content["plan"]["segment"],
            "accessSystem": content["plan"]["accessSystem"],
            "coverages": [
                {
                    "code": c["code"], "name": c["name"], "limits": c["limits"], "participation": c["participation"],
                    "waiting": c["waiting"], "requiresPriorApproval": c["requiresPriorApproval"],
                }
                for c in contracted
            ],
            "franchise": content["participationOption"],
            "waiting": content["waiting"],
            "exclusions": content["exclusions"],
            "conditions": content["conditions"],
        }
    return draft


@transaction.atomic
def emit_policy(
    *,
    quote: Quote,
    signatory_name: str,
    signatory_document_type: str,
    signatory_document_number: str,
    signatory_capacity: str,
    signature_method: str,
    signed_at: datetime.datetime,
    term_months: int,
    payment_frequency: str,
    requested_start_date: datetime.date | None,
    row_version: int,
    payment: dict[str, Any] | None,
    correlation_id: str | None,
) -> Policy:
    """Assinatura + (opcionalmente) 1.ª prestação paga + apólice digital.

    Sem `payment`, a apólice fica a aguardar o pagamento (PENDING_FIRST_PREMIUM)
    e o GTE regista-o depois no endpoint de pagamento já existente."""
    policy = issuance_service.issue_policy(
        quote=quote,
        signatory_name=signatory_name,
        signatory_document_type=signatory_document_type,
        signatory_document_number=signatory_document_number,
        signatory_capacity=signatory_capacity,
        signature_method=signature_method,
        signed_at=signed_at,
        term_months=term_months,
        payment_frequency=payment_frequency,
        requested_start_date=requested_start_date,
        row_version=row_version,
        correlation_id=correlation_id,
    )
    if payment is not None:
        policy = issuance_service.register_first_premium_payment(
            policy=policy,
            paid_at=payment["paidAt"],
            payment_reference=payment.get("paymentReference"),
            payment_method=payment.get("paymentMethod"),
            row_version=policy.row_version,
            correlation_id=correlation_id,
        )

    policy_document.store_policy_document(policy)

    from apps.customer_portal.application import requests_service

    requests_service.complete_accept_requests_for_quote(quote_id=quote.id, policy_number=policy.policy_number)
    return policy

