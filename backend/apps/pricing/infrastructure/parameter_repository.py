"""Read-side lookup of a published `PricingParameterSet` by business key
(code) and reference date — same shape as
`apps.pricing.application.rating_table_service.resolve_rating_table`, just
for the sibling `apps.product.infrastructure.models.PricingParameterSet`
(Q360-S2-03). See OPEN_DECISIONS.md#S04-CROSS-MODULE-001 for why pricing
reads product's model directly instead of through a port.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db.models import Q

from apps.product.domain.enums import VersionedConfigStatus
from apps.product.infrastructure.models import PricingParameter, PricingParameterSet


def resolve_pricing_parameter_set(*, code: str, effective_date: datetime.date) -> PricingParameterSet | None:
    return (
        PricingParameterSet.objects.filter(
            code=code, status=VersionedConfigStatus.PUBLISHED.value, effective_from__lte=effective_date
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )


def resolve_decimal_parameter(parameter_set: PricingParameterSet, parameter_code: str) -> Decimal | None:
    parameter = (
        PricingParameter.objects.filter(parameter_set=parameter_set, parameter_code=parameter_code)
        .order_by("-created_at")
        .first()
    )
    if parameter is None or parameter.value_type != "DECIMAL" or parameter.decimal_value is None:
        return None
    return parameter.decimal_value
