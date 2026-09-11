"""Status/type enumerations — values copied verbatim from ART-005 CHECK
constraints (ART-006 schema enums agree). Do not add a value that is not
in both.

`relationship_code` (ART-005 `insured_member.relationship_code`) has
deliberately NO enum here: no approved document defines the set of valid
relationship codes (DOC-004 s8 claims "finalized in ART-011", but
ART-011's own Code Catalogues sheet has no such entry — see
OPEN_DECISIONS.md#S03-RELATIONSHIP-001). It is a free `varchar(40)` in V1.
"""
from __future__ import annotations

from enum import Enum


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
