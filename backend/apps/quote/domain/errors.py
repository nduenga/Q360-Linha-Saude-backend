"""Domain errors for the quote module."""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class ReferencedEntityNotFoundError(DomainProblem):
    """A referenced `proposerId`/`planId`/`memberId` does not resolve to a
    real row for this tenant (or, for `createQuote`, the plan is not
    ACTIVE — DECISIONS_TAKEN.md#S09-POLICY-001). None of the Quote endpoints'
    ART-006 response sets include a 400 that maps this specifically, but
    `createQuote`/`addQuoteMember` do declare 400 (BadRequest) — same
    reasoning as apps.eligibility/apps.pricing's own
    ReferencedEntityNotFoundError."""

    http_status = 400
    problem_code = "VALIDATION-400"


class QuoteStateError(DomainProblem):
    """An operation was attempted from a `Quote.status` that does not allow
    it (ART-009 "Quote Machine" sheet, ART-006 `QUOTE-STATE` error code)."""

    http_status = 409
    problem_code = "QUOTE-STATE"


class RowVersionMismatchError(DomainProblem):
    """Optimistic locking conflict (ART-006 `QuoteUpdateRequest.rowVersion`)."""

    http_status = 409
    problem_code = "VERSION-CONFLICT"


class DuplicateMemberError(DomainProblem):
    """The member is already associated with this quote
    (`uq_quote_member`, ART-012 V020)."""

    http_status = 409
    problem_code = "CONFLICT"


class SegregationOfDutiesError(DomainProblem):
    """The actor deciding (approve/reject/return) is the same actor who
    submitted the quote — forbidden by `ck_quote_four_eyes`/
    `ck_decision_four_eyes` (ART-012 V019/V023) and Q360-S7-01's own
    acceptance criterion ("Submitter não aprova")."""

    http_status = 403
    problem_code = "SEC-403"


class QuoteDeletionBlockedError(DomainProblem):
    """A Quote cannot be deleted because it is in a protected status
    (APPROVED / IN_REVIEW / BOUND) — decisions by an approver have been
    registered and the quote may have downstream documents or policies.
    Users should CANCEL or REJECT the quote instead to keep the audit trail.
    Alternatively ask a product admin to delete it manually if the quote
    was created by accident (no approver touches)."""

    http_status = 409
    problem_code = "QUOTE-DELETE-BLOCKED"
