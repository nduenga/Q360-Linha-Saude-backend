"""Domain errors for the quote module."""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class ReferencedEntityNotFoundError(DomainProblem):
    """A referenced `proposerId`/`productVersionId`/`planId`/`memberId` does
    not resolve to a real row for this tenant. None of the Quote endpoints'
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
