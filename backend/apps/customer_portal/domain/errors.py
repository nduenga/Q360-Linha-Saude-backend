"""Domain errors for the customer portal — a new, isolated actor/contract
(ROADMAP_PORTAL_CLIENTE.md Fase 0), not governed by ART-006's closed
`x-q360-error-catalog` (that catalog only covers the staff/backoffice
API). `PORTAL-LOCKED`/`PORTAL-POLICY-NOT-FOUND`/`PORTAL-REGISTRATION-
MISMATCH` are new codes, added to
`apps.foundation.interfaces.exception_handler._TITLES`.

Product Owner decision (2026-09-26): request-access tells the caller
exactly which of policyNumber/registrationNumber is wrong, instead of the
original always-202/never-reveal-anything design (see git history on this
file for that version). This is a deliberate trade of anti-enumeration
secrecy for clearer feedback to a genuine customer - compensating control:
`apps.customer_portal.interfaces.rate_limit.is_ip_rate_limited`, a much
tighter, email-independent-key limit on this specific endpoint (the old
per-email bucket alone is trivially bypassed once the caller can vary the
email field, which is never itself verified before this point).

DECISIONS_TAKEN.md#S09-POLICY-001/Fase 6 (2026-09-28): login now resolves
by `Policy.policyNumber`, not `Quote.quoteNumber` — `PortalQuoteNotFoundError`
was renamed to `PortalPolicyNotFoundError`
(`PORTAL-QUOTE-NOT-FOUND` -> `PORTAL-POLICY-NOT-FOUND`), a breaking
change to this endpoint's error contract, not kept backward-compatible
(no stable external consumer of the old code existed yet)."""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class PortalPolicyNotFoundError(DomainProblem):
    """No ACTIVE/EXPIRED Policy matches the given policyNumber at all."""

    http_status = 404
    problem_code = "PORTAL-POLICY-NOT-FOUND"


class PortalRegistrationMismatchError(DomainProblem):
    """policyNumber resolved to a real Policy, but registrationNumber does
    not match that Policy's Proposer."""

    http_status = 401
    problem_code = "PORTAL-REGISTRATION-MISMATCH"


class InvalidPortalCredentialsError(DomainProblem):
    """The OTP itself is wrong/expired/already used, or verify-otp was
    called for an email that never actually requested access for this
    policyNumber/registrationNumber pair (call request-access first)."""

    http_status = 401
    problem_code = "AUTH-401"


class PortalAccountLockedError(DomainProblem):
    """OD-PORTAL-003 (Product Owner decision 2026-09-22): reached after 5
    failed attempts; the account stays locked for 30 minutes."""

    http_status = 423
    problem_code = "PORTAL-LOCKED"


class PortalResourceNotFoundError(DomainProblem):
    """Fase 1/6 (ROADMAP_PORTAL_CLIENTE.md): a `policyNumber`/`memberId`
    supplied by the authenticated customer does not resolve to something
    linked to their own `customer_account` proposers. Deliberately the
    same 404 whether the resource doesn't exist at all or belongs to a
    different customer — never confirms another customer's policy
    exists. Reuses the generic NOT-FOUND catalog code (this is a plain
    instance of it, not a portal-specific situation)."""

    http_status = 404
    problem_code = "NOT-FOUND"


class PortalNoEmailOnFileError(DomainProblem):
    """The proposer exists and the document matches, but the platform has no
    email for them — a first-access code has nowhere to go. The mediator has
    to register the email (or invite the customer)."""

    http_status = 409
    problem_code = "PORTAL-NO-EMAIL"


class PortalLegacyLoginDisabledError(DomainProblem):
    """The old policyNumber+document+email OTP login is switched off
    (`CUSTOMER_PORTAL_LEGACY_LOGIN_ENABLED=false`)."""

    http_status = 404
    problem_code = "NOT-FOUND"
