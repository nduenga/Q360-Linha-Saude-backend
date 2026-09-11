"""Status enumerations — values copied verbatim from ART-005 CHECK
constraints (ART-006 schema enums agree)."""
from __future__ import annotations

from enum import Enum


class VersionedConfigStatus(str, Enum):
    """ART-005 `ck_rating_status`; ART-006 `VersionedConfigHeader.status`.
    Duplicated from apps.product.domain.enums (identical DRAFT/PUBLISHED/
    RETIRED lifecycle) rather than imported — `pricing` and `product` are
    sibling modules, importing between them would create an undeclared
    dependency (DOC-004 s3.1)."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class PricingRunStatus(str, Enum):
    """ART-012 V015 `ck_pricing_status`; ART-009 PricingRun state machine."""

    REQUESTED = "REQUESTED"
    CALCULATING = "CALCULATING"
    CALCULATED = "CALCULATED"
    FAILED = "FAILED"


class PricingComponentType(str, Enum):
    """ART-012 V016 `ck_pricing_component_type`; ART-006 `PricingComponent.type`."""

    BASE = "BASE"
    FACTOR = "FACTOR"
    ADJUSTMENT = "ADJUSTMENT"
    FEE = "FEE"
    TAX = "TAX"
    TOTAL = "TOTAL"
    OTHER = "OTHER"
