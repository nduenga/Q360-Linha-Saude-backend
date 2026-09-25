"""Product/ProductVersion/Plan orchestration (Q360-S2-01, S2-02).

Plain functions rather than one-class-per-operation: DOC-004 s7 only names
a dedicated use case for the operation with a real invariant to protect
(`PublishProductVersionUseCase`, see use_cases.py) — everyday create/update
is plumbing, not modelled as a separate class in the source document.
"""
from __future__ import annotations

import uuid
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.application.benefit_service import (
    add_plan_benefit,
    attach_core_benefits,
    core_benefit_ids,
    resolve_complementary_benefits,
)
from apps.product.domain.enums import ProductStatus, VersionedConfigStatus
from apps.product.domain.errors import (
    DuplicateCodeError,
    DuplicatePlanCoverageSetError,
    EffectiveDateOverlapError,
    ImmutableVersionError,
    RowVersionMismatchError,
)
from apps.product.infrastructure.models import Plan, PlanBenefit, Product, ProductVersion

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def create_product(*, code: str, name: str, description: str | None) -> Product:
    # Product Owner decision (2026-09-25): a Product is ACTIVE from the
    # moment it is created - an inactive product has no reason to exist in
    # the catalogue, so there is no useful DRAFT holding state before a
    # future product-management page can move it to INACTIVE/ARCHIVED (or
    # briefly back to DRAFT for rework) via `PUT .../status`. This is the
    # only thing that changed here: DRAFT/INACTIVE/ARCHIVED remain valid,
    # reachable ProductStatus values, just never the *creation* default
    # anymore (model field default stays DRAFT - only this service call
    # overrides it, so nothing else needs to change).
    tenant_id = CurrentTenantProvider.require()
    try:
        with transaction.atomic():
            product = Product.objects.create(
                tenant_id=tenant_id.value,
                code=code,
                name=name,
                description=description,
                status=ProductStatus.ACTIVE.value,
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
    # Captured before the UPDATE below overwrites them - see the
    # content_changed check further down (Product Owner requirement: a new
    # ProductVersion only rolls forward when name/description actually
    # change, never for e.g. a status-only edit).
    content_changed = product.name != name or product.description != description

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

    # ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 2: an edit to a Product that
    # actually changes name/description rolls its version forward
    # automatically — the explicit "create version" step no longer exists
    # from the caller's perspective for that case. A product with no
    # version yet has nothing to roll forward (its first version is still
    # created explicitly, once a Plan exists to put in it). A status-only
    # edit (or a PUT that resends the same name/description) must NOT
    # trigger a version rollover — Product Owner requirement: creating a
    # new Plan is a completely separate action from creating a new
    # ProductVersion, and only name/description changes justify a new one.
    if content_changed and ProductVersion.objects.filter(product=product).exclude(
        status=VersionedConfigStatus.RETIRED.value
    ).exists():
        create_next_version(product=product)

    return product


def create_next_version(*, product: Product) -> ProductVersion:
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 2 + 3: replaces the old
    explicit "create version" step. Retires the current latest (non-
    RETIRED) version, creates the next one effective today with no end
    date (Épico 3: a product is never given an expiry), copies every Plan
    and its PlanBenefit rows across unchanged, and publishes it
    immediately (OD-ANGOLA-003 resolved as auto-publish: a single "edit
    product" action should not require a separate manual publish step).

    Existing Quotes/PricingRuns are unaffected: they pin a specific
    ProductVersion by id, and retiring a version never deletes it or the
    rows that reference it (OD-ANGOLA-004).
    """
    with transaction.atomic():
        locked_product = Product.objects.select_for_update().get(id=product.id)
        previous = (
            ProductVersion.objects.select_for_update()
            .filter(product=locked_product)
            .exclude(status=VersionedConfigStatus.RETIRED.value)
            .order_by("-version_no")
            .first()
        )
        today = timezone.now().date()
        next_version_no = (previous.version_no if previous else 0) + 1
        actor = CurrentActorProvider.get()

        if previous is not None:
            ProductVersion.objects.filter(id=previous.id).update(
                status=VersionedConfigStatus.RETIRED.value, effective_to=today
            )

        version = ProductVersion.objects.create(
            tenant_id=CurrentTenantProvider.require().value,
            product=locked_product,
            version_no=next_version_no,
            effective_from=today,
            effective_to=None,
            status=VersionedConfigStatus.PUBLISHED.value,
            published_at=timezone.now(),
            published_by=actor.actor_id if actor else None,
        )

        if previous is not None:
            for plan in previous.plans.all():
                new_plan = Plan.objects.create(
                    tenant_id=version.tenant_id,
                    product_version=version,
                    code=plan.code,
                    name=plan.name,
                    description=plan.description,
                )
                for plan_benefit in plan.plan_benefits.all():
                    PlanBenefit.objects.create(
                        tenant_id=version.tenant_id,
                        plan=new_plan,
                        benefit=plan_benefit.benefit,
                        configuration_json=plan_benefit.configuration_json,
                    )

    _audit.record(
        action="product_version.created",
        entity_type="ProductVersion",
        entity_id=str(version.id),
        metadata={"productId": str(product.id), "versionNo": version.version_no, "auto": True},
    )
    _outbox.append(
        aggregate_type="ProductVersion",
        aggregate_id=str(version.id),
        event_type="PRODUCT.VERSION.PUBLISHED",
        payload={
            "productVersionId": str(version.id),
            "productId": str(product.id),
            "versionNo": version.version_no,
            "publishedAt": version.published_at.isoformat() if version.published_at else None,
            "publishedBy": version.published_by,
        },
    )
    return version


def _versions_overlap(
    a_from: date, a_to: date | None, b_from: date, b_to: date | None
) -> bool:
    # Half-open interval overlap test; a missing "to" means "open-ended".
    a_end = a_to if a_to is not None else date.max
    b_end = b_to if b_to is not None else date.max
    return a_from <= b_end and b_from <= a_end


def create_product_version(*, product: Product, effective_from: date) -> ProductVersion:
    # ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 3: a ProductVersion is never
    # given an expiry — `effective_to` is always None, so the only way an
    # existing version stops being current is being RETIRED (see
    # create_next_version below, the normal path once a product already
    # has a version). This function remains for a product's very first
    # version, before there is anything to roll forward from.
    #
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
            if _versions_overlap(effective_from, None, other.effective_from, other.effective_to):
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
            effective_to=None,
        )

    _audit.record(
        action="product_version.created",
        entity_type="ProductVersion",
        entity_id=str(version.id),
        metadata={"productId": str(product.id), "versionNo": version.version_no},
    )
    return version


def create_plan(
    *,
    product_version: ProductVersion,
    code: str,
    name: str,
    description: str | None,
    complementary_benefit_ids: list[uuid.UUID] | None = None,
) -> Plan:
    tenant_id = CurrentTenantProvider.require().value
    # Resolved *before* the locked transaction below: a bad id here must
    # 400 (InvalidBenefitSelectionError) without ever touching a row lock.
    complementary_benefits = resolve_complementary_benefits(
        tenant_id=tenant_id, benefit_ids=complementary_benefit_ids or []
    )
    candidate_coverage_ids = core_benefit_ids(tenant_id) | {b.id for b in complementary_benefits}

    # `select_for_update()` closes a race against a concurrent publish of
    # the same version: without it, this check and
    # `PublishProductVersionUseCase`'s conditional UPDATE could each read
    # DRAFT before the other commits, letting a plan attach to a version
    # that ends up PUBLISHED (DOC-004 s7: "publicação é operação explícita"
    # / immutable once published). The same lock also serialises concurrent
    # create_plan() calls against this version, which is what makes the
    # duplicate-coverage-set check below race-free (no DB constraint can
    # express "no two rows share the same computed set").
    try:
        with transaction.atomic():
            locked_version = ProductVersion.objects.select_for_update().get(id=product_version.id)
            if locked_version.status != VersionedConfigStatus.DRAFT.value:
                raise ImmutableVersionError(
                    f"ProductVersion {locked_version.id} is {locked_version.status}; "
                    "plans can only be added to a DRAFT version"
                )

            # Product Owner requirement: a Plan's coverages are its only
            # real differentiator, so no two Plans of the same
            # ProductVersion may end up with the exact same coverage set -
            # this also covers "at most one basic plan" for free, since an
            # empty `complementary_benefit_ids` candidate set equals BASE
            # coverages only, same as any other existing basic plan's.
            for existing_plan in Plan.objects.filter(product_version=locked_version):
                existing_ids = set(
                    PlanBenefit.objects.filter(plan=existing_plan).values_list("benefit_id", flat=True)
                )
                if existing_ids == candidate_coverage_ids:
                    raise DuplicatePlanCoverageSetError(
                        f"Plan '{existing_plan.code}' already has this exact set of coverages "
                        f"in product version {locked_version.id}"
                    )

            plan = Plan.objects.create(
                tenant_id=tenant_id,
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
    for benefit in complementary_benefits:
        add_plan_benefit(plan=plan, benefit=benefit)

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


def update_plan(*, plan: Plan, name: str, description: str | None, row_version: int) -> Plan:
    """Only while the parent ProductVersion is DRAFT - same invariant
    create_plan() already enforces for adding a Plan in the first place
    (DOC-004 s7: immutable once published; a PUBLISHED version's plans are
    exactly what a Quote already priced against). Coverages are edited
    separately (PlanBenefitListCreateView/PlanBenefitDetailView, still
    DRAFT-gated the same way via the plan's own version) - this only
    covers name/description, mirroring update_product()'s optimistic
    locking via rowVersion."""
    with transaction.atomic():
        locked_version = ProductVersion.objects.select_for_update().get(id=plan.product_version_id)
        if locked_version.status != VersionedConfigStatus.DRAFT.value:
            raise ImmutableVersionError(
                f"ProductVersion {locked_version.id} is {locked_version.status}; "
                "a Plan can only be edited while its version is DRAFT"
            )
        updated = Plan.objects.filter(id=plan.id, row_version=row_version).update(
            name=name, description=description, row_version=row_version + 1
        )
    if updated == 0:
        raise RowVersionMismatchError(
            f"Plan {plan.id} rowVersion {row_version} does not match the current version"
        )
    plan.refresh_from_db()
    _audit.record(
        action="plan.updated", entity_type="Plan", entity_id=str(plan.id), metadata={"rowVersion": plan.row_version}
    )
    return plan


def delete_plan(*, plan: Plan) -> None:
    """Only while the parent ProductVersion is DRAFT - same reasoning as
    update_plan(). `plan_benefit` has no `ON DELETE CASCADE`
    (0001_product_baseline.py), so attached benefits are deleted first,
    same pattern as delete_pricing_parameter_set/delete_rating_table."""
    with transaction.atomic():
        locked_version = ProductVersion.objects.select_for_update().get(id=plan.product_version_id)
        if locked_version.status != VersionedConfigStatus.DRAFT.value:
            raise ImmutableVersionError(
                f"ProductVersion {locked_version.id} is {locked_version.status}; "
                "a Plan can only be deleted while its version is DRAFT"
            )
        PlanBenefit.objects.filter(plan_id=plan.id).delete()
        Plan.objects.filter(id=plan.id).delete()
    _audit.record(action="plan.deleted", entity_type="Plan", entity_id=str(plan.id), metadata={"code": plan.code})