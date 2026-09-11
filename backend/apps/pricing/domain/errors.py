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
