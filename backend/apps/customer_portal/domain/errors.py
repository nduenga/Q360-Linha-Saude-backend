"""Domain errors for the customer portal — a new, isolated actor/contract
(ROADMAP_PORTAL_CLIENTE.md Fase 0), not governed by ART-006's closed
`x-q360-error-catalog` (that catalog only covers the staff/backoffice
API). `PORTAL-LOCKED` is a new code, added to
`apps.foundation.interfaces.exception_handler._TITLES`; the credentials
error reuses the existing generic `AUTH-401` since the situation really is
a plain "not authenticated" one.
"""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class InvalidPortalCredentialsError(DomainProblem):
    """quoteNumber/registrationNumber/email do not resolve to a match, or
    the OTP is wrong/expired/already used. Deliberately one generic error
    for all of these — never reveals which part failed, so a caller can't
    use the response to confirm a real quoteNumber/document exists."""

    http_status = 401
    problem_code = "AUTH-401"


class PortalAccountLockedError(DomainProblem):
    """OD-PORTAL-003 (Product Owner decision 2026-09-22): reached after 5
    failed attempts; the account stays locked for 30 minutes."""

    http_status = 423
    problem_code = "PORTAL-LOCKED"
