"""Experience-rating calculation shared by claims reporting and quote pricing.

The factor is fully parameterized by the published business configuration.
It is applied only when there is sufficient imported history for the chosen
metric; otherwise callers receive a clear unavailable result.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from apps.business_config.application.readers import BusinessSnapshot
from apps.claims.application import summary_service


def calculate(*, proposer_id, policy_id=None, currency: str | None = "AOA", on: datetime.date | None = None,
              record_audit: bool = False) -> dict[str, Any]:
    day = on or datetime.date.today()
    config = BusinessSnapshot.load(on=day).get("pricing.experience_rating")
    if not config or not config.get("enabled"):
        return {"available": False, "reason": "NOT_CONFIGURED"}
    if not currency:
        return {"available": False, "reason": "CURRENCY_UNKNOWN"}
    months = int(config["lookback_months"])
    start_index = day.year * 12 + day.month - months
    date_from = datetime.date(start_index // 12, start_index % 12 + 1, 1)
    try:
        data = summary_service.summary(
            proposer_id=proposer_id, policy_id=policy_id, date_from=date_from, date_to=day,
            currency=currency, record_audit=record_audit,
        )
    except summary_service.ClaimsDataError:
        return {"available": False, "reason": "NO_CLAIMS_HISTORY", "lookbackMonths": months}
    metric = config["metric"]
    observed_by_metric = {
        "LOSS_RATIO": data.get("lossRatioPct"),
        "CLAIMS_FREQUENCY": data["claims"].get("frequencyPerInsuredYear"),
        "CLAIMS_SEVERITY": data["claims"].get("averageCost"),
    }
    observed_raw = observed_by_metric.get(metric)
    if observed_raw is None:
        return {"available": False, "reason": "INSUFFICIENT_HISTORY", "metric": metric,
                "lookbackMonths": months, "period": data["period"]}
    observed = Decimal(str(observed_raw))
    target = Decimal(str(config["target_value"]))
    if target <= 0:
        return {"available": False, "reason": "INVALID_TARGET", "metric": metric}
    weight = Decimal(str(config["weight_percent"])) / Decimal("100")
    raw_factor = Decimal("1") + (observed - target) / target * weight
    factor = min(Decimal(str(config["maximum_factor"])),
                 max(Decimal(str(config["minimum_factor"])), raw_factor))
    return {
        "available": True, "metric": metric, "observedValue": str(observed), "targetValue": str(target),
        "weightPercent": str(config["weight_percent"]), "lookbackMonths": months,
        "period": data["period"], "unclampedFactor": str(raw_factor), "factor": str(factor),
        "clamped": factor != raw_factor,
    }
