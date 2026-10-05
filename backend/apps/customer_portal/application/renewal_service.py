"""Jornada de renovação (PDF s.11) e comparação de planos (PDF s.12).

A renovação não tem lógica nova: junta o que já existe — a apólice, a cotação
de renovação (`Quote.quote_type="RENEWAL"`, `source_policy_id`) e o pedido
`RENEWAL`/`ACCEPT_QUOTE` — e diz ao cliente em que passo está. A emissão
continua a ser do backoffice (a assinatura é registada por quem emite).

A comparação mostra só o que o cliente precisa para escolher — coberturas,
limites, carências, participação — e nunca preços, tabelas de tarifação ou
regras internas (PDF s.19)."""
from __future__ import annotations

import datetime
from typing import Any

from apps.customer_portal.application.portal_read import policy_phase
from apps.customer_portal.application.requests_service import RENEWAL_WINDOW_DAYS
from apps.customer_portal.application.self_service import portal_quote_item, portal_quote_status, resolve_my_policy
from apps.customer_portal.infrastructure.models import PortalRequest
from apps.customer_portal.domain import requests as rules
from apps.policy.infrastructure.models import PolicyMember, PremiumInstallment
from apps.pricing.domain.money import round_amount
from apps.product.application.benefit_service import list_plan_benefits
from apps.product.infrastructure.models import Plan
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote

STEPS = (
    ("ALERT", "Alerta de aproximação do vencimento"),
    ("CONDITIONS", "Consulta das condições actuais"),
    ("UPDATE", "Actualização de informações"),
    ("REQUEST", "Pedido de renovação"),
    ("PROPOSAL", "Recepção da proposta de renovação"),
    ("ACCEPTANCE", "Aceitação pelo cliente"),
    ("ISSUANCE", "Emissão da renovação"),
)


def get_renewal(policy_number: str, *, today: datetime.date | None = None) -> dict:
    today = today or datetime.date.today()
    policy = resolve_my_policy(policy_number)
    days_left = (policy.end_date - today).days if policy.end_date else None
    window_open = policy.status == "ACTIVE" and days_left is not None and 0 <= days_left <= RENEWAL_WINDOW_DAYS

    renewal_quote = (
        Quote.objects.filter(source_policy_id=policy.id, quote_type="RENEWAL")
        .exclude(status=QuoteStatus.DRAFT.value)
        .select_related("plan__product", "latest_pricing_run")
        .order_by("-created_at")
        .first()
    )
    quote_status = portal_quote_status(renewal_quote, today) if renewal_quote else None
    renewal_request = PortalRequest.objects.filter(policy_id=policy.id, request_type="RENEWAL").order_by("-created_at").first()
    open_request = renewal_request is not None and renewal_request.status in rules.OPEN_STATUSES
    accept_request = (
        PortalRequest.objects.filter(quote_id=renewal_quote.id, request_type="ACCEPT_QUOTE").exists()
        if renewal_quote else False
    )
    renewed = policy.status == "RENEWED" or quote_status == "CONTRACTED"

    done = {
        "ALERT": window_open or renewed or policy_phase(policy, today) == "EXPIRING",
        "CONDITIONS": window_open or renewed,
        "UPDATE": renewal_request is not None or renewal_quote is not None or renewed,
        "REQUEST": renewal_request is not None or renewal_quote is not None or renewed,
        "PROPOSAL": quote_status in ("AWAITING_SIGNATURE", "CONTRACTED") or renewed,
        "ACCEPTANCE": accept_request or quote_status == "CONTRACTED" or renewed,
        "ISSUANCE": renewed,
    }
    current_found = False
    steps = []
    for code, label in STEPS:
        if done[code]:
            state = "DONE"
        elif not current_found:
            state, current_found = "CURRENT", True
        else:
            state = "PENDING"
        steps.append({"code": code, "label": label, "state": state})

    installments = list(PremiumInstallment.objects.filter(policy=policy).exclude(status="VOID"))
    total = sum((i.amount for i in installments), start=0)
    return {
        "policyNumber": policy.policy_number,
        "policyStatus": policy.status,
        "endDate": policy.end_date,
        "daysLeft": days_left,
        "windowDays": RENEWAL_WINDOW_DAYS,
        "canRequest": window_open and not open_request and renewal_quote is None,
        "currentTerms": {
            "product": {"name": policy.plan.product.name} if policy.plan.product else None,
            "plan": {"name": policy.plan.name},
            "startDate": policy.start_date,
            "endDate": policy.end_date,
            "paymentFrequency": policy.payment_frequency,
            "currencyCode": policy.currency_code,
            "totalPremium": str(round_amount(total)) if installments else None,
            "insuredPeople": PolicyMember.objects.filter(policy=policy, status="ACTIVE").count(),
        },
        "request": (
            {"requestNumber": renewal_request.request_number, "status": renewal_request.status,
             "statusLabel": rules.STATUS_LABELS[renewal_request.status]}
            if renewal_request else None
        ),
        "proposal": portal_quote_item(renewal_quote, policy_number=None, today=today) if renewal_quote else None,
        "steps": steps,
    }


# ------------------------------------------------------- plan comparison
def _limits(config: dict[str, Any]) -> list[dict]:
    result = []
    for limit in config.get("limits") or []:
        if not isinstance(limit, dict):
            continue
        result.append({k: limit[k] for k in ("kind", "label", "amount", "count", "pct") if limit.get(k) is not None})
    return result


def _participation(config: dict[str, Any]) -> dict:
    result = {}
    for block, spec in (config.get("participation") or {}).items():
        if isinstance(spec, dict):
            result[block] = {
                k: spec[k] for k in ("type", "copayAmount", "insurerPct", "insuredAnnualCap") if spec.get(k) is not None
            }
    return result


def _plan_row(plan: Plan, *, current: bool) -> dict:
    benefits = []
    for plan_benefit in list_plan_benefits(plan=plan):
        config = plan_benefit.configuration_json or {}
        benefits.append(
            {
                "code": plan_benefit.benefit.code,
                "name": plan_benefit.benefit.name,
                "category": plan_benefit.benefit.benefit_type,
                "inclusion": config.get("inclusion", "INCLUDED"),
                "currency": config.get("currency", "AOA"),
                "limits": _limits(config),
                "waitingDays": config.get("waitingDays"),
                "requiresPriorApproval": bool(config.get("requiresPriorApproval", False)),
                "participation": _participation(config),
            }
        )
    return {"code": plan.code, "name": plan.name, "description": plan.description, "isCurrent": current, "benefits": benefits}


def compare_plans(policy_number: str) -> dict:
    """Plans of the same product as the caller's policy, side by side."""
    policy = resolve_my_policy(policy_number)
    plans = list(Plan.objects.filter(product_id=policy.plan.product_id, status="ACTIVE").order_by("name"))
    if all(p.id != policy.plan_id for p in plans):
        plans.append(policy.plan)
    rows = [_plan_row(plan, current=plan.id == policy.plan_id) for plan in plans]
    catalogue: dict[str, dict] = {}
    for row in rows:
        for benefit in row["benefits"]:
            catalogue.setdefault(benefit["code"], {"code": benefit["code"], "name": benefit["name"], "category": benefit["category"]})
    return {
        "policyNumber": policy.policy_number,
        "product": {"name": policy.plan.product.name} if policy.plan.product else None,
        "plans": rows,
        "benefits": sorted(catalogue.values(), key=lambda b: (b["category"] or "", b["name"])),
    }
