"""PricingParameterSet orchestration (Q360-S2-03).

`create_pricing_parameter_set` receives already-typed, already-validated
parameter rows (see interfaces/serializers.py `PricingParameterValueSerializer`,
which dispatches ART-006 `PricingParameterValue.valueType` to the matching
ART-005 discriminated-union column) — this layer only persists and audits.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.domain.enums import VersionedConfigStatus
from apps.product.domain.errors import DuplicateCodeError, ImmutableVersionError
from apps.product.infrastructure.models import PricingParameter, PricingParameterSet

_audit = AuditService(DjangoAuditRepositoryAdapter())


def create_pricing_parameter_set(
    *, code: str, effective_from: date, effective_to: date | None, parameter_rows: list[dict[str, Any]]
) -> PricingParameterSet:
    tenant_id = CurrentTenantProvider.require()
    try:
        with transaction.atomic():
            # No explicit row lock for the version_no read below (unlike
            # ProductVersion, PricingParameterSet has no natural parent row
            # to lock): a concurrent duplicate is instead caught by the
            # `uq_pricing_parameter_set` DB constraint, converted to a
            # clean 409 DuplicateCodeError by the `except IntegrityError`
            # below — safe (no corruption), just occasionally a "retry".
            next_version_no = (
                PricingParameterSet.objects.filter(code=code)
                .order_by("-version_no")
                .values_list("version_no", flat=True)
                .first()
                or 0
            ) + 1
            parameter_set = PricingParameterSet.objects.create(
                tenant_id=tenant_id.value,
                code=code,
                version_no=next_version_no,
                effective_from=effective_from,
                effective_to=effective_to,
            )
            PricingParameter.objects.bulk_create(
                [
                    PricingParameter(tenant_id=tenant_id.value, parameter_set=parameter_set, **row)
                    for row in parameter_rows
                ]
            )
    except IntegrityError as exc:
        raise DuplicateCodeError(
            f"PricingParameterSet '{code}' could not be created: version already exists, "
            "or a parameterCode is duplicated within the set"
        ) from exc

    _audit.record(
        action="pricing_parameter_set.created",
        entity_type="PricingParameterSet",
        entity_id=str(parameter_set.id),
        metadata={"code": code, "versionNo": parameter_set.version_no, "parameterCount": len(parameter_rows)},
    )
    return parameter_set


def publish_pricing_parameter_set(parameter_set: PricingParameterSet) -> PricingParameterSet:
    actor = CurrentActorProvider.get()
    # Conditional UPDATE, not read-then-save — see PublishProductVersionUseCase
    # for why this matters under concurrent publish attempts.
    updated = PricingParameterSet.objects.filter(
        id=parameter_set.id, status=VersionedConfigStatus.DRAFT.value
    ).update(
        status=VersionedConfigStatus.PUBLISHED.value,
        published_at=timezone.now(),
        published_by=actor.actor_id if actor else None,
    )
    if updated == 0:
        raise ImmutableVersionError(
            f"PricingParameterSet {parameter_set.id} is not DRAFT; only DRAFT can be published"
        )
    parameter_set.refresh_from_db()

    _audit.record(
        action="pricing_parameter_set.published",
        entity_type="PricingParameterSet",
        entity_id=str(parameter_set.id),
        metadata={"code": parameter_set.code, "versionNo": parameter_set.version_no},
    )
    return parameter_set
