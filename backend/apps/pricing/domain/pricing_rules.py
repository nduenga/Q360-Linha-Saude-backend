"""Optional pricing adjustment rules (Q360-S5-01), read the same way
`apps.eligibility.domain.evaluation.EligibilityRuleConfig` reads its
config: parsed from a tenant's published `RuleVersion.artifact_ref`
(rule_domain=PRICING, artifact_type=JSON).

OPEN DECISION — see backend/OPEN_DECISIONS.md#S05-PRICING-RULES-001: no
approved artifact defines what a "Drools rule" actually contains for
pricing. DOC-003's S5-01 says "Drools integration + rule resolver", but
ART-006's `RuleSetVersionRequest` only ever carries an opaque
`artifactRef`/`artifactChecksum` pointer (`artifactType`: DRL /
DECISION_TABLE / JSON / INTERNAL) — no artifact ships an executable rule
DSL or its semantics. This mirrors ELIG-008/009's `Criterion`: a
deliberately minimal, generic, additive-adjustment placeholder so the
engine and its API are real and testable, not a stand-in for a real
Drools/DMN engine.
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclasses.dataclass(frozen=True, slots=True)
class PricingAdjustment:
    """One entry of `adjustments`. All `when` keys must match (AND) the
    member's calculation context for this adjustment to apply."""

    code: str
    when: dict[str, Any]
    amount: Decimal

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PricingAdjustment | None":
        code = raw.get("code")
        amount_raw = raw.get("amount")
        if not code or not isinstance(amount_raw, str):
            return None
        try:
            amount = Decimal(amount_raw)
        except InvalidOperation:
            return None
        when = raw.get("when")
        return cls(code=code, when=when if isinstance(when, dict) else {}, amount=amount)

    def matches(self, context: dict[str, Any]) -> bool:
        return all(context.get(k) == v for k, v in self.when.items())


@dataclasses.dataclass(frozen=True, slots=True)
class PricingRuleConfig:
    """Parsed `RuleVersion.artifact_ref` (artifact_type=JSON) for a
    published rule_domain=PRICING version."""

    adjustments: tuple[PricingAdjustment, ...] = ()

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "PricingRuleConfig":
        raw_adjustments = raw.get("adjustments", [])
        if not isinstance(raw_adjustments, list):
            raw_adjustments = []
        parsed = [PricingAdjustment.from_dict(a) for a in raw_adjustments if isinstance(a, dict)]
        return cls(adjustments=tuple(a for a in parsed if a is not None))
