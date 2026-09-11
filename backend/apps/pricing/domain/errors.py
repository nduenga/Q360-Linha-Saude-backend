"""Domain errors for the pricing module."""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class DuplicateCodeError(DomainProblem):
    """A `(code, versionNo)` that must be unique is already in use."""

    http_status = 409
    problem_code = "CONFLICT"


class ImmutableVersionError(DomainProblem):
    """Publishing something that is not DRAFT (already published/retired)."""

    http_status = 409
    problem_code = "CONFLICT"


class ReferencedEntityNotFoundError(DomainProblem):
    """`productVersionId`/`planId`/a memberId does not resolve to a real
    row for this tenant. `calculatePricing`'s response set (ART-006) has
    no 404, so this is a request error (400) — same reasoning as
    apps.eligibility.domain.errors.ReferencedEntityNotFoundError."""

    http_status = 400
    problem_code = "VALIDATION-400"


class PricingConfigError(DomainProblem):
    """No applicable published RatingTable/PricingParameterSet/parameter
    for the requested context ("Regra/configuração impede processamento"
    -> ART-006 `responses/Unprocessable`, 422)."""

    http_status = 422
    problem_code = "PRICING-CONFIG"


class PricingCalculationFailedError(DomainProblem):
    """The calculation started (PricingRun exists) but could not complete
    -> ART-009 PricingRun transitions to FAILED. Q360-S5-03's "negative/
    overflow" guards raise this."""

    http_status = 422
    problem_code = "PRICING-FAILED"
