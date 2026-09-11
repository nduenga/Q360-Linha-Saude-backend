"""Money/rounding policy (Q360-S4-03).

OPEN DECISION — OD-002 (backend/OPEN_DECISIONS.md#S04-ROUNDING-001): no
approved Q360 document fixes the official currency/rounding policy.
ART-006's own `x-q360-open-decisions` lists `OD-002: Moeda e política
oficial de arredondamento`, and ART-013's only "official" pricing golden
test (`PENDING_OD_pricing_template.json`, caseId GT-PRICE-OFFICIAL-001) is
itself `status: PENDING_OD`, blocked on OD-001/OD-002.

This module implements an explicit, versioned, swappable placeholder
policy instead of an implicit float truncation — satisfying S4-03's actual
acceptance criteria ("rounding mode explícito", "total reconcilia")
without pretending a business decision has been made. The policy
code/version are recorded on every `PricingRun` precisely so a future real
policy change is auditable and never silently reinterprets a past run.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

PLACEHOLDER_ROUNDING_POLICY_CODE = "OD-002-PLACEHOLDER-HALF-UP-2DP"
PLACEHOLDER_ROUNDING_POLICY_VERSION = 1

_MINOR_UNIT_QUANTUM = Decimal("0.01")


def round_amount(value: Decimal) -> Decimal:
    """Round to 2 decimal places (minor currency unit) via ROUND_HALF_UP.

    Not a business-approved policy — see module docstring. Every monetary
    `PricingComponent.resultAmount` is rounded at the point it is computed
    (not just the final total), so the visible components always sum
    exactly to `PricingResponse.totalAmount` with no unexplained residue.
    """
    return value.quantize(_MINOR_UNIT_QUANTUM, rounding=ROUND_HALF_UP)
