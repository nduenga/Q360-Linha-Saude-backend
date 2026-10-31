"""Status/type enumerations — values copied verbatim from ART-005 CHECK
constraints (ART-006 schema enums agree). Do not add a value that is not
in both.

`relationship_code` (ART-005 `insured_member.relationship_code`) stays a
free `varchar(40)` at the DB level — no approved document defines the set
of valid relationship codes as an ART-005/ART-012 enum (DOC-004 s8 claims
"finalized in ART-011", but ART-011's own Code Catalogues sheet has no
such entry). What changed (OPEN_DECISIONS.md#S03-RELATIONSHIP-001,
Product Owner decision 2026-09-21, OD-003): a real, DB-backed catalog
table (`RelationshipCode`, apps/client/infrastructure/models.py) now
supplies the actual valid values per tenant, validated at the application
layer (apps/client/application/member_service.py) — `RelationshipCategory`
below is that catalog's own `category` column, a pragmatic V1
classification, not an ART-005 enum.
"""
from __future__ import annotations

from enum import Enum


class RelationshipCategory(str, Enum):
    """`relationship_code.category` (pragmatic V1 addition, see module
    docstring) — broad classification a future eligibility rule (OD-005)
    can key off (e.g. "children lose eligibility at 18/25", "ascendants
    require proof of cohabitation or financial dependency") without
    hardcoding every individual relationship code."""

    TITULAR = "TITULAR"
    COLLABORATOR = "COLLABORATOR"
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    DESCENDANT = "DESCENDANT"
    ASCENDANT = "ASCENDANT"
    OTHER = "OTHER"


class ProposerType(str, Enum):
    """ART-005 `ck_proposer_type`; ART-006 `Proposer.proposerType`."""

    INDIVIDUAL = "INDIVIDUAL"
    ORGANISATION = "ORGANISATION"


class ProposerStatus(str, Enum):
    """ART-005 `ck_proposer_status`; ART-006 `Proposer.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MemberStatus(str, Enum):
    """ART-005 `ck_member_status`; ART-006 `Member.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ImportJobStatus(str, Enum):
    """ART-005 `ck_import_status`; ART-006 `ImportJob.status`."""

    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    COMMITTING = "COMMITTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImportType(str, Enum):
    """ART-005 `ck_import_type` — currently a single allowed value."""

    MEMBER_POPULATION = "MEMBER_POPULATION"
