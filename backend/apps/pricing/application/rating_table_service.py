"""RatingTable/RatingFactor orchestration (Q360-S4-01).

`resolve_factor` is the read-side lookup the pricing engine (Q360-S4-02)
uses to apply a factor for a given business key (e.g. an age band, a
relationship code) — DOC-002 s"Sprint 4": "Selecção de tarifa por chave de
negócio e data de referência."
"""
from __future__ import annotations

import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.domain.enums import VersionedConfigStatus
from apps.pricing.domain.errors import DuplicateCodeError, ImmutableVersionError
from apps.pricing.infrastructure.models import RatingFactor, RatingTable

_audit = AuditService(DjangoAuditRepositoryAdapter())


def create_rating_table(
    *,
    code: str,
    name: str,
    effective_from: datetime.date,
    effective_to: datetime.date | None,
    currency_code: str | None,
    factor_rows: list[dict[str, Any]],
) -> RatingTable:
    tenant_id = CurrentTenantProvider.require()
    try:
        with transaction.atomic():
            next_version_no = (
                RatingTable.objects.filter(code=code)
                .order_by("-version_no")
                .values_list("version_no", flat=True)
                .first()
                or 0
            ) + 1
            rating_table = RatingTable.objects.create(
                tenant_id=tenant_id.value,
                code=code,
                name=name,
                version_no=next_version_no,
                effective_from=effective_from,
                effective_to=effective_to,
                currency_code=currency_code,
            )
            RatingFactor.objects.bulk_create(
                [
                    RatingFactor(
                        tenant_id=tenant_id.value,
                        rating_table=rating_table,
                        factor_code=row["factorCode"],
                        dimension_json=row["dimensions"],
                        factor_value=row["factorValue"],
                        priority=row.get("priority", 0),
                    )
                    for row in factor_rows
                ]
            )
    except IntegrityError as exc:
        raise DuplicateCodeError(f"RatingTable '{code}' could not be created: version already exists") from exc

    _audit.record(
        action="rating_table.created",
        entity_type="RatingTable",
        entity_id=str(rating_table.id),
        metadata={"code": code, "versionNo": rating_table.version_no, "factorCount": len(factor_rows)},
    )
    return rating_table


def publish_rating_table(rating_table: RatingTable) -> RatingTable:
    actor = CurrentActorProvider.get()
    updated = RatingTable.objects.filter(id=rating_table.id, status=VersionedConfigStatus.DRAFT.value).update(
        status=VersionedConfigStatus.PUBLISHED.value,
        published_at=timezone.now(),
        published_by=actor.actor_id if actor else None,
    )
    if updated == 0:
        raise ImmutableVersionError(f"RatingTable {rating_table.id} is not DRAFT; only DRAFT can be published")
    rating_table.refresh_from_db()

    _audit.record(
        action="rating_table.published",
        entity_type="RatingTable",
        entity_id=str(rating_table.id),
        metadata={"code": rating_table.code, "versionNo": rating_table.version_no},
    )
    return rating_table


def resolve_rating_table(*, code: str, effective_date: datetime.date) -> RatingTable | None:
    from django.db.models import Q

    return (
        RatingTable.objects.filter(code=code, status=VersionedConfigStatus.PUBLISHED.value, effective_from__lte=effective_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )


def resolve_factor(*, rating_table: RatingTable, factor_code: str, context: dict[str, Any]) -> RatingFactor | None:
    """Highest-priority `RatingFactor` whose `dimension_json` is fully
    satisfied by `context` (i.e. `dimension_json` is a subset of
    `context`) — an empty `dimension_json` matches everything and acts as
    the lowest-priority fallback unless a more specific row outranks it.
    """
    return (
        RatingFactor.objects.filter(rating_table=rating_table, factor_code=factor_code, dimension_json__contained_by=context)
        .order_by("-priority")
        .first()
    )
