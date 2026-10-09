"""Automatic RatingTable/PricingParameterSet resolution for Quote pricing
(Q360-S6-03).

ART-006's `QuotePriceRequest` is just `{recalculate: bool}` — there is no
`context` field at all, so the caller can never name a
`ratingTableCode`/`parameterSetCode` (the same gap as
OPEN_DECISIONS.md#S04-PRICING-CONTEXT-001, but here entirely outside the
client's control). This mirrors the identical convention already
implemented client-side in the frontend's `PricingPage.tsx`
(`resolveLatestPerCode`): resolve the single PUBLISHED code effective on
the date if unambiguous, else fail closed (`PricingConfigError`) rather
than guess — the same Admin-configures/system-resolves split documented in
`DECISIONS_TAKEN.md#S04-PRICING-CONTEXT-001`.
"""
from __future__ import annotations

import datetime

from django.db.models import Q

from apps.pricing.domain.enums import VersionedConfigStatus as PricingConfigStatus
from apps.pricing.domain.errors import PricingConfigError
from apps.pricing.infrastructure.models import RatingTable
from apps.product.domain.enums import VersionedConfigStatus as ProductConfigStatus
from apps.product.infrastructure.models import PricingParameterSet


def _single_published_code(codes: list[str], *, resource_name: str) -> str:
    distinct = sorted(set(codes))
    if len(distinct) == 0:
        raise PricingConfigError(f"Não há nenhum(a) {resource_name} publicado(a) configurado(a) para esta data")
    if len(distinct) > 1:
        raise PricingConfigError(
            f"Existem vários códigos publicados de {resource_name} ({', '.join(distinct)}): é ambíguo; um administrador tem de retirar os que não estão em uso"
        )
    return distinct[0]


def resolve_default_rating_table_code(*, effective_date: datetime.date) -> str:
    codes = list(
        RatingTable.objects.filter(status=PricingConfigStatus.PUBLISHED.value, effective_from__lte=effective_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .values_list("code", flat=True)
        .distinct()
    )
    return _single_published_code(codes, resource_name="rating table")


def resolve_default_parameter_set_code(*, effective_date: datetime.date) -> str:
    codes = list(
        PricingParameterSet.objects.filter(
            status=ProductConfigStatus.PUBLISHED.value, effective_from__lte=effective_date
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .values_list("code", flat=True)
        .distinct()
    )
    return _single_published_code(codes, resource_name="parameter set")
