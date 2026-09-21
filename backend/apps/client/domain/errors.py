"""Domain errors for the client module. Each subclasses
`apps.foundation.domain.problem.DomainProblem`, reusing ART-006's closed
`x-q360-error-catalog` codes (see apps/product/domain/errors.py for the
full rationale — DOC-003's illustrative `CLIENT-*`/`MEMBER-*`/`IMPORT-*`
prefixes are not in ART-006's actual catalog, so these situations reuse
the existing generic codes instead of inventing new ones).
"""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem


class DuplicateExternalReferenceError(DomainProblem):
    """`externalReference` must be unique per tenant (Proposer) or per
    tenant+proposer (Member) when provided."""

    http_status = 409
    problem_code = "CONFLICT"


class RowVersionMismatchError(DomainProblem):
    """Optimistic-locking `rowVersion` supplied by the client does not
    match the current persisted value."""

    http_status = 409
    problem_code = "VERSION-CONFLICT"


class IncoherentDateError(DomainProblem):
    """DOC-003 Q360-S3-02 acceptance criterion "Datas coerentes" — e.g. a
    `dateOfBirth` in the future."""

    http_status = 400
    problem_code = "VALIDATION-400"


class UnknownRelationshipCodeError(DomainProblem):
    """OD-003 (OPEN_DECISIONS.md#S03-RELATIONSHIP-001): `relationshipCode`
    must be one of the tenant's real catalogue values (GET
    /api/v1/relationship-codes), not an arbitrary string."""

    http_status = 400
    problem_code = "VALIDATION-400"


class ImportCommitNotAllowedError(DomainProblem):
    """`commitMemberImport` called on a job that is not VALIDATED (already
    committed, still validating, or failed)."""

    http_status = 409
    problem_code = "CONFLICT"
