"""Domain errors for the eligibility module."""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class ReferencedEntityNotFoundError(DomainProblem):
    """`planId` does not resolve to a real row. Cannot be
    recorded as a HARD_STOP `EligibilityEvaluation` because ART-005 declares
    both columns `NOT NULL` — there is nothing to persist. `evaluateEligibility`
    has no 404 in its response set (ART-006), so this maps to 400."""

    http_status = 400
    problem_code = "VALIDATION-400"
