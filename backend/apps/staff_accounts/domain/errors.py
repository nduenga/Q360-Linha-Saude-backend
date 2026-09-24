"""Domain errors for self-hosted staff identity (replaces the external
Auth0 IdP — DOC-004 s6.1's `JwtActorAdapter` is unchanged, only who issues
the token is new). Same posture as `apps.customer_portal.domain.errors`:
a new contract, not governed by ART-006's closed error catalog.
"""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class InvalidStaffCredentialsError(DomainProblem):
    """Wrong email/password, or the account does not exist/is disabled -
    deliberately one generic error for all three, never reveals which
    (same reasoning as InvalidPortalCredentialsError: never confirm a
    real email/account exists to an unauthenticated caller)."""

    http_status = 401
    problem_code = "AUTH-401"


class StaffAccountLockedError(DomainProblem):
    """Reached after too many failed login attempts (Q360_STAFF_MAX_FAILED_ATTEMPTS)."""

    http_status = 423
    problem_code = "STAFF-LOCKED"


class DuplicateStaffAccountEmailError(DomainProblem):
    """`email` must be unique per tenant (staff_account)."""

    http_status = 409
    problem_code = "CONFLICT"


class InvalidRefreshTokenError(DomainProblem):
    """Refresh token missing, expired, revoked, or already rotated once
    (reuse of a rotated token is treated as a possible compromise - see
    StaffAccountAuthService.refresh)."""

    http_status = 401
    problem_code = "AUTH-401"
