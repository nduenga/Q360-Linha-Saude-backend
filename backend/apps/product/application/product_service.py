"""Product/ProductVersion/Plan orchestration (Q360-S2-01, S2-02).

Plain functions rather than one-class-per-operation: DOC-004 s7 only names
a dedicated use case for the operation with a real invariant to protect
(`PublishProductVersionUseCase`, see use_cases.py) — everyday create/update
is plumbing, not modelled as a separate class in the source document.
"""
from __future__ import annotations

from datetime import date

from django.db import IntegrityError, transaction

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.domain.enums import VersionedConfigStatus
from apps.product.domain.errors import (
    DuplicateCodeError,
    EffectiveDateOverlapError,
    ImmutableVersionError,
    RowVersionMismatchError,
)
from apps.product.application.benefit_service import attach_core_benefits
from apps.product.infrastructure.models import Plan, Product, ProductVersion

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def create_product(*, code: str, name: str, description: str | None) -> Product:
    tenant_id = CurrentTenantProvider.require()
    try:
        with transaction.atomic():
            product = Product.objects.create(
                tenant_id=tenant_id.value, code=code, name=name, description=description
            )
    except IntegrityError as exc:
        raise DuplicateCodeError(f"Product code '{code}' already exists for this tenant") from exc

    _audit.record(action="product.created", entity_type="Product", entity_id=str(product.id))
    return product


def update_product(
    *, product: Product, name: str, description: str | None, row_version: int, status: str | None = None
) -> Product:
    # DOC-004 s7 invariant enforcement via optimistic locking (ART-006
    # ProductUpdateRequest.rowVersion): an UPDATE that does not match the
    # currently persisted row_version affects zero rows, which is how we
    # detect the conflict without a separate SELECT ... FOR UPDATE race.
    #
    # `status` is a pragmatic V1 addition, not in ART-006's
    # ProductUpdateRequest (see OPEN_DECISIONS.md#S04-LISTING-GAPS-001/
    # DECISIONS_TAKEN.md#product-status-transition): the contract has no
    # documented way to move a Product out of DRAFT at all, and ART-011's
    # own seed data keeps its demo product in DRAFT forever by design
    # (CHK-008 "Draft-only commercial shells") — publishing a
    # ProductVersion never implicitly activates the parent Product, those
    # are two independent lifecycle fields (ART-005). Optional and
    # backward-compatible: omitted, behaviour is unchanged.
    fields = {"name": name, "description": description, "row_version": row_version + 1}
    if status is not None:
        fields["status"] = status
    updated = Product.objects.filter(id=product.id, row_version=row_version).update(**fields)
    if updated == 0:
        raise RowVersionMismatchError(
            f"Product {product.id} rowVersion {row_version} does not match the current version"
        )
    product.refresh_from_db()
    _audit.record(
        action="product.updated",
        entity_type="Product",
        entity_id=str(product.id),
        metadata={"rowVersion": product.row_version},
    )
    return product


def _versions_overlap(
    a_from: date, a_to: date | None, b_from: date, b_to: date | None
) -> bool:
    # Half-open interval overlap test; a missing "to" means "open-ended".
    a_end = a_to if a_to is not None else date.max
    b_end = b_to if b_to is not None else date.max
    return a_from <= b_end and b_from <= a_end


def create_product_version(
    *, product: Product, effective_from: date, effective_to: date | None
) -> ProductVersion:
    # DOC-004 s7 invariant: "vigências incompatíveis não se sobrepõem",
    # checked against every non-RETIRED version of the same product (DRAFT
    # included) — see domain/errors.py EffectiveDateOverlapError docstring
    # for why this is enforced at create time rather than publish time.
    #
    # The overlap check AND the version_no assignment both read the
    # product's existing versions, so both must happen after acquiring
    # `select_for_update()` on the parent Product row: that serialises
    # concurrent `create_product_version` calls for the same product,
    # closing a TOCTOU race where two overlapping/duplicate-version_no
    # versions could otherwise both pass their check before either commits.
    with transaction.atomic():
        locked_product = Product.objects.select_for_update().get(id=product.id)
        existing = ProductVersion.objects.filter(product=locked_product).exclude(
            status=VersionedConfigStatus.RETIRED.value
        )
        for other in existing:
            if _versions_overlap(effective_from, effective_to, other.effective_from, other.effective_to):
                raise EffectiveDateOverlapError(
                    f"Effective range overlaps existing version {other.version_no} of product {product.id}"
                )

        next_version_no = (
            existing.order_by("-version_no").values_list("version_no", flat=True).first() or 0
        ) + 1
        version = ProductVersion.objects.create(
            tenant_id=CurrentTenantProvider.require().value,
            product=locked_product,
            version_no=next_version_no,
            effective_from=effective_from,
            effective_to=effective_to,
        )

    _audit.record(
        action="product_version.created",
        entity_type="ProductVersion",
        entity_id=str(version.id),
        metadata={"productId": str(product.id), "versionNo": version.version_no},
    )
    return version


def create_plan(*, product_version: ProductVersion, code: str, name: str, description: str | None) -> Plan:
    # `select_for_update()` closes a race against a concurrent publish of
    # the same version: without it, this check and
    # `PublishProductVersionUseCase`'s conditional UPDATE could each read
    # DRAFT before the other commits, letting a plan attach to a version
    # that ends up PUBLISHED (DOC-004 s7: "publicação é operação explícita"
    # / immutable once published).
    try:
        with transaction.atomic():
            locked_version = ProductVersion.objects.select_for_update().get(id=product_version.id)
            if locked_version.status != VersionedConfigStatus.DRAFT.value:
                raise ImmutableVersionError(
                    f"ProductVersion {locked_version.id} is {locked_version.status}; "
                    "plans can only be added to a DRAFT version"
                )
            plan = Plan.objects.create(
                tenant_id=CurrentTenantProvider.require().value,
                product_version=locked_version,
                code=code,
                name=name,
                description=description,
            )
    except IntegrityError as exc:
        raise DuplicateCodeError(
            f"Plan code '{code}' already exists for product version {product_version.id}"
        ) from exc

    # ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1: every Plan always carries the
    # 3 market-mandatory (BASE) coverages — never something a caller opts
    # into, and never skippable, so it happens here rather than in the view.
    attach_core_benefits(plan=plan)

    _audit.record(action="plan.created", entity_type="Plan", entity_id=str(plan.id))
    _outbox.append(
        aggregate_type="Plan",
        aggregate_id=str(plan.id),
        event_type="PLAN.CREATED",
        payload={
            "planId": str(plan.id),
            "productVersionId": str(product_version.id),
            "code": plan.code,
            "name": plan.name,
        },
    )
    return plan
