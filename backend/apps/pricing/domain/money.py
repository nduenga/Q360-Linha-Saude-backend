"""Money/rounding policy (Q360-S4-03).

RESOLVED — backend/OPEN_DECISIONS.md#S04-ROUNDING-001 (Product Owner
decision, 2026-09-21, OD-006): AOA (Kwanza) is the official currency, and
every monetary amount rounds to 2 decimal places via ROUND_HALF_UP
("quando tiver 3 casas decimais, arredonda para cima"). This is now the
real, approved business policy, not a placeholder pending approval. `TST`
remains reserved for ART-013's purely technical golden-test fixtures
(never real/demo business data) — this decision does not touch that
convention.

The policy code/version are still recorded on every `PricingRun`, exactly
as before, so a future policy change (if ever needed) stays auditable and
never silently reinterprets a past run.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ROUNDING_POLICY_CODE = "OD-006-OFFICIAL-HALF-UP-2DP"
ROUNDING_POLICY_VERSION = 1

_MINOR_UNIT_QUANTUM = Decimal("0.01")


def round_amount(value: Decimal) -> Decimal:
    """Round to 2 decimal places (minor currency unit) via ROUND_HALF_UP —
    the official policy (see module docstring). Every monetary
    `PricingComponent.resultAmount` is rounded at the point it is computed
    (not just the final total), so the visible components always sum
    exactly to `PricingResponse.totalAmount` with no unexplained residue.
    """
    return value.quantize(_MINOR_UNIT_QUANTUM, rounding=ROUND_HALF_UP)
