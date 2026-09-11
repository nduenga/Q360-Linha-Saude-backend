"""Status/type enumerations — values copied verbatim from ART-005 CHECK
constraints and ART-006 schema enums (both agree). Do not add a value that
is not in both.
"""
from __future__ import annotations

from enum import Enum


class ProductStatus(str, Enum):
    """ART-005 `ck_product_status`; ART-006 `Product.status`."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class VersionedConfigStatus(str, Enum):
    """ART-005 `ck_product_version_status` / `ck_pps_status`; ART-006
    `ProductVersion.status` / `VersionedConfigHeader.status`. Shared by
    ProductVersion and PricingParameterSet — both use the identical
    DRAFT/PUBLISHED/RETIRED lifecycle in ART-005/ART-006.
    """

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class PlanStatus(str, Enum):
    """ART-005 `ck_plan_status`; ART-006 `Plan.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class BenefitStatus(str, Enum):
    """ART-005 `ck_benefit_status`. No ART-006 endpoint exists for Benefit
    yet — see OPEN_DECISIONS.md#S02-CONTRACT-001."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PricingParameterValueType(str, Enum):
    """ART-005 `ck_pricing_parameter_type`; ART-006
    `PricingParameterValue.valueType`."""

    DECIMAL = "DECIMAL"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    TEXT = "TEXT"
    JSON = "JSON"
