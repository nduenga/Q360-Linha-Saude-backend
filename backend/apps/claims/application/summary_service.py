"""Indicadores de sinistralidade (R2): loss ratio, frequência, custo médio,
histórico disponível e participação nos resultados do grupo.

Fórmulas (explícitas na resposta; a confirmar com o cliente — OPEN_DECISIONS):
  sinistros      = pagos + provisões (linhas `REJECTED` não contam)
  prémio ganho   = Σ prémio × dias de sobreposição / dias do período
  loss ratio     = sinistros / prémio ganho × 100
  frequência     = n.º de sinistros / anos-pessoa  (anos-pessoa = Σ pessoas × dias/365)
  custo médio    = sinistros / n.º de sinistros
  participação   = prémio ganho × max(0, limite − loss ratio)/100 × quota/100
                   (PDF: devolução de parte do prémio se a sinistralidade
                   ficar abaixo do limite acordado, ex. 65 %)

Só devolve agregados: nenhuma linha de sinistro individual sai da API
(dados de saúde) e cada leitura fica em auditoria.
"""
from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import Any

from apps.claims.infrastructure.models import ClaimRecord, PremiumRecord
from apps.foundation.application.audit_service import AuditService
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter

_audit = AuditService(DjangoAuditRepositoryAdapter())
FORMULAS = {
    "claims": "pagos + provisões (linhas REJECTED excluídas)",
    "earnedPremium": "Σ prémio × dias de sobreposição / dias do período",
    "lossRatioPct": "sinistros / prémio ganho × 100",
    "frequency": "n.º de sinistros / anos-pessoa",
    "averageCost": "sinistros / n.º de sinistros",
}
TWO = Decimal("0.01")


class ClaimsDataError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _q(value: Decimal) -> str:
    return str(value.quantize(TWO))


def _months_between(start: datetime.date, end: datetime.date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def history_months(*, proposer_id, currency: str | None = None) -> int:
    """Months of history available for a client (claims and premiums)."""
    dates: list[datetime.date] = []
    claims = ClaimRecord.objects.filter(proposer_id=proposer_id)
    premiums = PremiumRecord.objects.filter(proposer_id=proposer_id)
    if currency:
        claims, premiums = claims.filter(currency_code=currency), premiums.filter(currency_code=currency)
    dates += list(claims.values_list("occurrence_date", flat=True))
    for start, end in premiums.values_list("period_start", "period_end"):
        dates += [start, end]
    return _months_between(min(dates), max(dates)) if dates else 0


def summary(
    *, proposer_id, policy_id=None, date_from=None, date_to=None, currency: str = "AOA", record_audit: bool = True
) -> dict[str, Any]:
    claims = ClaimRecord.objects.filter(proposer_id=proposer_id, currency_code=currency).exclude(status="REJECTED")
    premiums = PremiumRecord.objects.filter(proposer_id=proposer_id, currency_code=currency)
    if policy_id:
        claims, premiums = claims.filter(policy_id=policy_id), premiums.filter(policy_id=policy_id)
    claim_rows = list(claims.values("occurrence_date", "benefit_code", "paid_amount", "provision_amount"))
    premium_rows = list(premiums.values("period_start", "period_end", "premium_amount", "insured_count"))
    if not claim_rows and not premium_rows:
        raise ClaimsDataError(f"Não há sinistros nem prémios importados para este cliente em {currency}")

    all_dates = [r["occurrence_date"] for r in claim_rows]
    for r in premium_rows:
        all_dates += [r["period_start"], r["period_end"]]
    start = date_from or min(all_dates)
    end = date_to or max(all_dates)
    if end < start:
        raise ClaimsDataError("'to' é anterior a 'from'")

    in_range = [r for r in claim_rows if start <= r["occurrence_date"] <= end]
    paid = sum((r["paid_amount"] for r in in_range), Decimal("0"))
    provision = sum((r["provision_amount"] for r in in_range), Decimal("0"))
    total_claims = paid + provision

    earned = Decimal("0")
    person_years: Decimal | None = Decimal("0")
    insured_known = True
    for r in premium_rows:
        overlap_start, overlap_end = max(start, r["period_start"]), min(end, r["period_end"])
        overlap = (overlap_end - overlap_start).days + 1
        if overlap <= 0:
            continue
        period_days = (r["period_end"] - r["period_start"]).days + 1
        earned += r["premium_amount"] * Decimal(overlap) / Decimal(period_days)
        if r["insured_count"]:
            person_years += Decimal(r["insured_count"]) * Decimal(overlap) / Decimal(365)
        else:
            insured_known = False
    if not insured_known or person_years == 0:
        person_years = None

    by_benefit: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in in_range:
        amount = r["paid_amount"] + r["provision_amount"]
        by_benefit[r["benefit_code"]] += amount
        by_month[r["occurrence_date"].strftime("%Y-%m")] += amount

    count = len(in_range)
    result = {
        "proposerId": str(proposer_id),
        "currencyCode": currency,
        "period": {"from": start.isoformat(), "to": end.isoformat(), "months": _months_between(start, end)},
        "historyMonths": _months_between(min(all_dates), max(all_dates)),
        "premium": {"earned": _q(earned), "insuredYears": _q(person_years) if person_years is not None else None},
        "claims": {
            "count": count,
            "paid": _q(paid),
            "provision": _q(provision),
            "total": _q(total_claims),
            "averageCost": _q(total_claims / count) if count else None,
            "frequencyPerInsuredYear": _q(Decimal(count) / person_years) if person_years and count else None,
        },
        "lossRatioPct": _q(total_claims / earned * Decimal("100")) if earned > 0 else None,
        "byBenefit": [
            {"benefitCode": code, "total": _q(amount), "sharePct": _q(amount / total_claims * Decimal("100")) if total_claims else None}
            for code, amount in sorted(by_benefit.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "byMonth": [{"month": month, "total": _q(amount)} for month, amount in sorted(by_month.items())],
        "formulas": FORMULAS,
    }
    if record_audit:
        _audit.record(
            action="claims.summary_viewed", entity_type="Proposer", entity_id=str(proposer_id),
            metadata={"result": "SUCCESS", "from": start.isoformat(), "to": end.isoformat(), "currency": currency},
        )
    return result


def profit_sharing(
    *, proposer_id, threshold_pct: Decimal, share_pct: Decimal, policy_id=None, date_from=None, date_to=None, currency: str = "AOA"
) -> dict[str, Any]:
    data = summary(proposer_id=proposer_id, policy_id=policy_id, date_from=date_from, date_to=date_to, currency=currency)
    earned = Decimal(data["premium"]["earned"])
    if data["lossRatioPct"] is None:
        raise ClaimsDataError("A participação nos resultados precisa de prémio adquirido no período")
    loss_ratio = Decimal(data["lossRatioPct"])
    below = loss_ratio < threshold_pct
    refund = earned * (threshold_pct - loss_ratio) / Decimal("100") * share_pct / Decimal("100") if below else Decimal("0")
    return {
        "proposerId": str(proposer_id),
        "currencyCode": currency,
        "period": data["period"],
        "earnedPremium": data["premium"]["earned"],
        "claimsTotal": data["claims"]["total"],
        "lossRatioPct": data["lossRatioPct"],
        "thresholdPct": _q(threshold_pct),
        "sharePct": _q(share_pct),
        "eligible": below,
        "refundAmount": _q(refund),
        "formula": "prémio ganho × max(0, limite − loss ratio)/100 × quota/100",
        "indicative": True,
    }
