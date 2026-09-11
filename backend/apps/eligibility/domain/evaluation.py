"""Pure evaluation logic for Q360-S3-03, driven entirely by ART-008's Rule
Matrix ("Rule Matrix" sheet, rules ELIG-001..ELIG-010) — see
OPEN_DECISIONS.md#S03-ELIGIBILITY-001 for exactly which rules are final
(status PUBLISHED-CANDIDATE, no open parameter) versus provisional (status
DRAFT, thresholds/criteria unresolved per OD-004).

No business threshold (a minimum age, an allowed relationship list, a
referral condition) is hardcoded here — they are all read from
`EligibilityRuleConfig`, itself parsed from a tenant's published
`RuleVersion.artifact_ref` (rule_domain=ELIGIBILITY). An unconfigured
threshold simply never fires (its rule is a no-op), rather than defaulting
to some invented number.
"""
from __future__ import annotations

import dataclasses
import datetime
from typing import Any

from apps.eligibility.domain.enums import EligibilityDecision


@dataclasses.dataclass(frozen=True, slots=True)
class EligibilityMessage:
    code: str
    severity: str  # INFO | WARNING | ERROR (ART-006 EligibilityResponse.messages[].severity)
    message: str


@dataclasses.dataclass(frozen=True, slots=True)
class Criterion:
    """One entry of `referralCriteria`/`warningCriteria`. All provided
    fields must match (AND) for this entry to match; a list of entries is
    OR'd. This shape is NOT sourced from any approved document — ART-008
    explicitly says "No medical criteria invented in V1" for the rules that
    use it (ELIG-008/009) — it is a deliberately minimal, generic
    placeholder mechanism so the engine and its API are real and testable
    while Actuarial/Product define actual criteria. See
    OPEN_DECISIONS.md#S03-ELIGIBILITY-001.
    """

    relationship_codes: frozenset[str] | None = None
    min_age: int | None = None
    max_age: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Criterion":
        codes = raw.get("relationshipCodes")
        return cls(
            relationship_codes=frozenset(codes) if codes else None,
            min_age=raw.get("minAge"),
            max_age=raw.get("maxAge"),
        )

    def matches(self, *, age: int | None, relationship_code: str) -> bool:
        if self.relationship_codes is not None and relationship_code not in self.relationship_codes:
            return False
        if self.min_age is not None and (age is None or age < self.min_age):
            return False
        if self.max_age is not None and (age is None or age > self.max_age):
            return False
        return self.relationship_codes is not None or self.min_age is not None or self.max_age is not None


@dataclasses.dataclass(frozen=True, slots=True)
class EligibilityRuleConfig:
    """Parsed `RuleVersion.artifact_ref` (artifact_type=JSON) for a
    published rule_domain=ELIGIBILITY version."""

    min_entry_age: int | None = None
    max_entry_age: int | None = None
    allowed_relationship_codes: frozenset[str] | None = None
    referral_criteria: tuple[Criterion, ...] = ()
    warning_criteria: tuple[Criterion, ...] = ()

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "EligibilityRuleConfig":
        codes = raw.get("allowedRelationshipCodes")
        return cls(
            min_entry_age=raw.get("minEntryAge"),
            max_entry_age=raw.get("maxEntryAge"),
            allowed_relationship_codes=frozenset(codes) if codes else None,
            referral_criteria=tuple(Criterion.from_dict(c) for c in raw.get("referralCriteria", [])),
            warning_criteria=tuple(Criterion.from_dict(c) for c in raw.get("warningCriteria", [])),
        )


def _age_on(date_of_birth: datetime.date, effective_date: datetime.date) -> int:
    years = effective_date.year - date_of_birth.year
    if (effective_date.month, effective_date.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


@dataclasses.dataclass(frozen=True, slots=True)
class EvaluationInput:
    member_id: str | None
    relationship_code: str | None
    date_of_birth: datetime.date | None
    product_version_id: str | None
    plan_id: str | None
    effective_date: datetime.date


@dataclasses.dataclass(frozen=True, slots=True)
class ProductVersionFacts:
    effective_from: datetime.date
    effective_to: datetime.date | None


@dataclasses.dataclass(frozen=True, slots=True)
class PlanFacts:
    is_active: bool


def evaluate(
    *,
    data: EvaluationInput,
    product_version: ProductVersionFacts | None,
    plan: PlanFacts | None,
    config: EligibilityRuleConfig | None,
) -> tuple[EligibilityDecision, list[EligibilityMessage]]:
    """Pure function: same inputs always produce the same decision (DOC-004
    s9/DOC-000 P-02 determinism). Rule IDs referenced in comments are
    ART-008 Rule Matrix rows.
    """
    # ELIG-001 — Completeness (PUBLISHED-CANDIDATE, no open parameter).
    if not (data.member_id and data.product_version_id and data.plan_id and data.effective_date):
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("VALIDATION-400", "ERROR", "Required input missing")
        ]

    # Referenced entities must actually exist — not itself an ART-008 rule
    # (which assumes they resolve), but a precondition for evaluating
    # ELIG-006/007 at all.
    if product_version is None or plan is None:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage(
                "ELIG-REFERENCE-NOT-FOUND", "ERROR", "Referenced productVersion or plan does not exist"
            )
        ]

    # ELIG-006 — Product version not effective.
    if data.effective_date < product_version.effective_from or (
        product_version.effective_to is not None and data.effective_date > product_version.effective_to
    ):
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage(
                "ELIG-PRODUCT-DATE", "ERROR", "Product version not effective on quote date"
            )
        ]

    # ELIG-007 — Plan inactive.
    if not plan.is_active:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("ELIG-PLAN-INACTIVE", "ERROR", "Selected plan is inactive")
        ]

    # ELIG-010 — No applicable rule version: fail closed (DOC-004 s9:
    # "CONFIG_ERROR nunca pode ser convertido silenciosamente em ELIGIBLE").
    if config is None:
        return EligibilityDecision.CONFIG_ERROR, [
            EligibilityMessage("ELIG-RULE-MISSING", "ERROR", "Eligibility configuration unavailable")
        ]

    age: int | None = None
    if data.date_of_birth is not None:
        age = _age_on(data.date_of_birth, data.effective_date)

    age_rule_configured = config.min_entry_age is not None or config.max_entry_age is not None
    # ELIG-002 — Age can be calculated (only relevant when an age rule is
    # actually configured; an unconfigured threshold must not force every
    # member to supply a date of birth).
    if age_rule_configured and age is None:
        return EligibilityDecision.CONFIG_ERROR, [
            EligibilityMessage(
                "PRICING-CONFIG", "ERROR", "Date of birth unavailable for age-based rule"
            )
        ]

    # ELIG-003 — Age below configured minimum.
    if config.min_entry_age is not None and age is not None and age < config.min_entry_age:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("ELIG-AGE-MIN", "ERROR", "Member below minimum entry age")
        ]
    # ELIG-004 — Age above configured maximum.
    if config.max_entry_age is not None and age is not None and age > config.max_entry_age:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("ELIG-AGE-MAX", "ERROR", "Member above maximum entry age")
        ]

    # ELIG-005 — Relationship not allowed by plan.
    if (
        config.allowed_relationship_codes is not None
        and data.relationship_code not in config.allowed_relationship_codes
    ):
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage(
                "ELIG-RELATIONSHIP", "ERROR", "Relationship not eligible for selected plan"
            )
        ]

    relationship_code = data.relationship_code or ""

    # ELIG-008 — Configured referral condition matched.
    if any(c.matches(age=age, relationship_code=relationship_code) for c in config.referral_criteria):
        return EligibilityDecision.REFERRAL, [
            EligibilityMessage("ELIG-REFERRAL", "WARNING", "Manual underwriting review required")
        ]

    # ELIG-009 — Configured warning matched.
    if any(c.matches(age=age, relationship_code=relationship_code) for c in config.warning_criteria):
        return EligibilityDecision.WARNING, [
            EligibilityMessage(
                "ELIG-WARNING", "WARNING", "Eligibility warning requires acknowledgement"
            )
        ]

    return EligibilityDecision.ELIGIBLE, [EligibilityMessage("ELIG-OK", "INFO", "Member is eligible")]
