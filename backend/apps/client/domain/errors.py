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


class DuplicateNifError(DomainProblem):
    """A NIF identifies at most one proposer inside a tenant."""

    http_status = 409
    problem_code = "CONFLICT"


class DuplicateMemberNifError(DomainProblem):
    """Decisão R1 (2026-10-14, revista 2026-10-15): o NIF de uma pessoa segura,
    quando indicado, identifica no máximo uma pessoa segura em cada tomador
    (a mesma pessoa pode ter ficha, com NIF, em tomadores diferentes)."""

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


class InvalidMemberDocumentError(DomainProblem):
    """Ficheiro ou tipo de documento inválido (formato, tamanho, tipo de evidência)."""

    http_status = 400
    problem_code = "VALIDATION-400"


class MemberDocumentNotFoundError(DomainProblem):
    """O documento (ou a pessoa segura) não existe neste tenant."""

    http_status = 404
    problem_code = "NOT-FOUND"


class MemberDocumentStateError(DomainProblem):
    """O documento já foi analisado."""

    http_status = 409
    problem_code = "CONFLICT"


class InvalidNifError(DomainProblem):
    """NIF fora do formato exigido para o tipo de proponente
    (INDIVIDUAL: 14 caracteres; ORGANISATION: 10 dígitos)."""

    http_status = 400
    problem_code = "VALIDATION-400"


class DateOfBirthRequiredError(DomainProblem):
    """A data de nascimento é obrigatória para proponentes individuais e
    para todas as pessoas seguras."""

    http_status = 400
    problem_code = "VALIDATION-400"


class TitularRequiredError(DomainProblem):
    """Tem de existir um titular ativo antes de outras relações."""

    http_status = 400
    problem_code = "VALIDATION-400"


class DuplicateTitularError(DomainProblem):
    """Um proponente individual só pode ter um titular ativo."""

    http_status = 409
    problem_code = "CONFLICT"


class BeneficiaryLimitExceededError(DomainProblem):
    """Excedido `client.individual_max_beneficiaries`."""

    http_status = 400
    problem_code = "VALIDATION-400"


class GenerationGapError(DomainProblem):
    """Filho/ascendente com diferença de idade inferior a 13 anos."""

    http_status = 400
    problem_code = "VALIDATION-400"


class ImportPopulationInvalidError(DomainProblem):
    """O conjunto de pessoas do ficheiro (mais as já existentes) viola as
    regras de titular / limite de beneficiários / diferença de idade."""

    http_status = 400
    problem_code = "VALIDATION-400"
