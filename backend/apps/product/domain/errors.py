"""Domain errors for the product module.

Each subclasses `apps.foundation.domain.problem.DomainProblem`, mapping to
one of ART-006's `x-q360-error-catalog` codes generically (see
`apps.foundation.interfaces.exception_handler`) — this reuse (not new
catalog codes) is how DOC-003's illustrative `PROD-*`/`PLAN-*`/`PR-*` error
prefixes are reconciled with ART-006's actual, closed catalog: ART-006 is
the later, more specialised artefact and has no such codes (DOC-004 s2
precedence rule), so these situations reuse the existing generic codes
instead of inventing new ones.
"""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class DuplicateCodeError(DomainProblem):
    """A `code` that must be unique (per tenant, or per tenant+parent) is
    already in use."""

    http_status = 409
    problem_code = "CONFLICT"


class ImmutableVersionError(DomainProblem):
    """An operation would mutate/delete something still referenced
    elsewhere — e.g. deleting a Product/Plan that a Quote, PricingRun or
    EligibilityEvaluation already points to (DECISIONS_TAKEN.md#S09-POLICY-001,
    PO-APO-6: since ProductVersion was retired, this is the only remaining
    use of this error — see product_service.delete_product/delete_plan)."""

    http_status = 409
    problem_code = "CONFLICT"


class RowVersionMismatchError(DomainProblem):
    """Optimistic-locking `rowVersion` supplied by the client does not
    match the current persisted value."""

    http_status = 409
    problem_code = "VERSION-CONFLICT"


class DuplicatePlanCoverageSetError(DomainProblem):
    """Two Plans of the same ProductVersion would end up with the exact
    same set of attached coverages (BASE + chosen COMPLEMENTARY ones) —
    a Plan's coverages are its only real differentiator, so this would be
    a functionally-duplicate plan. Covers both requirements from the
    Product Owner: no two plans with identical coverages, and at most one
    "basic" plan (BASE coverages only, no COMPLEMENTARY ones opted into)
    per ProductVersion — the latter is just the empty-selection case of
    the former."""

    http_status = 409
    problem_code = "CONFLICT"


class InvalidBenefitSelectionError(DomainProblem):
    """A `complementaryBenefitIds` entry does not resolve to an ACTIVE,
    COMPLEMENTARY Benefit of the caller's tenant — either unknown, or a
    BASE coverage (those are never opted into, they are always attached
    automatically)."""

    http_status = 400
    problem_code = "VALIDATION-400"


class MissingCoreBenefitsError(DomainProblem):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1: a ProductVersion cannot
    publish while any of its Plans is missing a BASE (mandatory market)
    coverage. Also raised (via the CoreBenefitRemovalError subclass in
    benefit_service.py) when someone tries to detach a BASE coverage from
    a Plan — never allowed."""

    http_status = 400
    problem_code = "VALIDATION-400"
