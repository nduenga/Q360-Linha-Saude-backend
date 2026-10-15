"""Domain errors for the policy module. Reuses ART-006's generic
`x-q360-error-catalog` codes where they fit (same reuse posture as
apps.product/apps.quote/apps.eligibility/apps.pricing — see those
modules' own domain/errors.py docstrings), since `apps.policy` has no
ART-006 contract at all to extend. `PolicyStateError` is new, same
posture as `PORTAL-*`/`STAFF-*` codes: a new module, not a Change Request
against ART-006 (DECISIONS_TAKEN.md#S09-POLICY-001)."""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class ReferencedEntityNotFoundError(DomainProblem):
    """A referenced quoteId/policyId/installment does not resolve to a
    real row for this tenant."""

    http_status = 400
    problem_code = "VALIDATION-400"


class PolicyStateError(DomainProblem):
    """An operation was attempted from a `Policy.status` (or `Quote.status`)
    that does not allow it — same posture as apps.quote's `QUOTE-STATE`."""

    http_status = 409
    problem_code = "POLICY-STATE"


class RowVersionMismatchError(DomainProblem):
    """Optimistic-locking conflict on `Policy.rowVersion`."""

    http_status = 409
    problem_code = "VERSION-CONFLICT"


class DuplicatePolicyError(DomainProblem):
    """The referenced Quote already produced a Policy (`uq_policy_source_quote`)."""

    http_status = 409
    problem_code = "CONFLICT"


class InvalidStartDateError(DomainProblem):
    """`requestedStartDate` violates OD-APO-003: it is not strictly after
    the signature date."""

    http_status = 400
    problem_code = "VALIDATION-400"
