"""Simulação de impacto de uma versão de configuração **antes de a publicar**
(R7: "editar parâmetros; aplicar; simular; versionar; auditar; reverter").

Reprecia uma amostra das cotações mais recentes do tenant duas vezes com o
mesmo motor — com a versão publicada em vigor e com a versão candidata
(rascunho ou outra qualquer) — e resume a diferença: prémio total antes/depois,
variação média e máxima (%) e as cotações mais afetadas. Nada é gravado
(`preview_pricing` reverte a transação) e nenhuma cotação muda.

Suporta tabelas de tarifação, conjuntos de parâmetros e regras de PRICING.
Regras de elegibilidade não têm impacto direto no prémio e ficam de fora.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from apps.foundation.domain.problem import DomainProblem
from apps.pricing.application.pricing_engine import preview_pricing
from apps.pricing.domain.money import round_amount
from apps.product.application import configuration_lifecycle
from apps.quote.application import quote_service
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote

_SAMPLE_STATUSES = (
    QuoteStatus.DRAFT.value,
    QuoteStatus.READY.value,
    QuoteStatus.IN_REVIEW.value,
    QuoteStatus.APPROVED.value,
)


class ImpactSimulationNotSupportedError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _total(run) -> dict[str, Any]:
    return {"totalAmount": str(round_amount(run.total_amount))}


def simulate_impact(*, config_type: str, config_id: uuid.UUID, limit: int = 50) -> dict[str, Any]:
    candidate = configuration_lifecycle.load(config_type, config_id)
    if config_type == "rule-version" and candidate.rule_set.rule_domain != "PRICING":
        raise ImpactSimulationNotSupportedError(
            "A simulação de impacto suporta tabelas de tarifação, conjuntos de parâmetros de preço e versões de regra de PRICING"
        )
    code = configuration_lifecycle.code_of(config_type, candidate)
    context_key = {"rating-table": "ratingTableCode", "pricing-parameter-set": "parameterSetCode", "rule-version": "ruleVersionCode"}[config_type]
    override_key = {"rating-table": "ratingTableId", "pricing-parameter-set": "parameterSetId", "rule-version": "ruleVersionId"}[config_type]

    quotes = list(Quote.objects.filter(status__in=_SAMPLE_STATUSES).order_by("-created_at")[: max(1, min(limit, 200))])
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    before_sum = after_sum = Decimal("0")
    for quote in quotes:
        context, member_ids = quote_service.build_pricing_context(quote)
        if not member_ids:
            skipped.append({"quoteId": str(quote.id), "reason": "NO_PRICEABLE_MEMBERS"})
            continue
        if context.get(context_key) not in (code, None):  # a quote priced with another code is not affected
            skipped.append({"quoteId": str(quote.id), "reason": "OTHER_CONFIGURATION_CODE"})
            continue
        try:
            baseline = preview_pricing(
                plan_id=quote.plan_id, effective_date=quote.reference_date, member_ids=member_ids,
                context=context, correlation_id=None, render=_total,
            )
            candidate_context = {**context, "configOverrides": {override_key: str(candidate.id)}}
            changed = preview_pricing(
                plan_id=quote.plan_id, effective_date=quote.reference_date, member_ids=member_ids,
                context=candidate_context, correlation_id=None, render=_total, allow_config_overrides=True,
            )
        except DomainProblem as exc:
            skipped.append({"quoteId": str(quote.id), "reason": f"CALCULATION_FAILED: {exc}"})
            continue
        before, after = Decimal(baseline["totalAmount"]), Decimal(changed["totalAmount"])
        before_sum += before
        after_sum += after
        pct = ((after - before) / before * Decimal("100")).quantize(Decimal("0.01")) if before else None
        rows.append(
            {
                "quoteId": str(quote.id),
                "quoteNumber": quote.quote_number,
                "before": str(round_amount(before)),
                "after": str(round_amount(after)),
                "delta": str(round_amount(after - before)),
                "deltaPercent": str(pct) if pct is not None else None,
            }
        )

    percentages = [Decimal(r["deltaPercent"]) for r in rows if r["deltaPercent"] is not None]
    rows.sort(key=lambda r: abs(Decimal(r["delta"])), reverse=True)
    average = (sum(percentages) / len(percentages)).quantize(Decimal("0.01")) if percentages else None
    return {
        "configType": config_type,
        "candidate": configuration_lifecycle.header(config_type, candidate),
        "sampled": len(quotes),
        "compared": len(rows),
        "skipped": skipped,
        "totals": {
            "before": str(round_amount(before_sum)),
            "after": str(round_amount(after_sum)),
            "delta": str(round_amount(after_sum - before_sum)),
            "deltaPercent": str(((after_sum - before_sum) / before_sum * Decimal("100")).quantize(Decimal("0.01"))) if before_sum else None,
        },
        "deltaPercent": {
            "average": str(average) if average is not None else None,
            "max": str(max(percentages)) if percentages else None,
            "min": str(min(percentages)) if percentages else None,
        },
        "mostAffected": rows[:10],
    }
