"""Product/Plan orchestration (Q360-S2-01, S2-02).

DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26): ProductVersion is
retired from the platform — a Plan belongs directly to a Product, and a
Plan's own `status` (ACTIVE/INACTIVE) does the job the version's
DRAFT/PUBLISHED/RETIRED lifecycle used to do: `ACTIVE` means "can start
new business", `INACTIVE` means "no longer sold, but still fully readable"
(existing Quotes/Policies never break — same OD-ANGOLA-004 guarantee as
before, just expressed one level down). There is no more DRAFT-gating on
a Plan's coverages: a Plan can be edited at any time, and what a Quote
actually contracted is protected by its own immutable snapshot
(apps.quote.application.quote_service._plan_content_snapshot), never by
the Plan being locked.

Plain functions rather than one-class-per-operation: DOC-004 s7 only names
a dedicated use case for the operation with a real invariant to protect —
everyday create/update is plumbing, not modelled as a separate class in
the source document.
"""
from __future__ import annotations

import uuid

from django.db import IntegrityError, transaction

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.application.benefit_service import (
    add_plan_benefit,
    attach_core_benefits,
    core_benefit_ids,
    resolve_complementary_benefits,
)
from apps.product.domain.enums import PlanStatus, ProductStatus
from apps.product.domain.plan_settings import validate_plan_settings
from apps.product.domain.errors import (
    DuplicateCodeError,
    DuplicatePlanCoverageSetError,
    ImmutableVersionError,
    RowVersionMismatchError,
)
from apps.product.infrastructure.models import Plan, PlanBenefit, Product

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
        raise DuplicateCodeError(f"O código de produto '{code}' já existe neste tenant") from exc

    _audit.record(
        action="product.created", entity_type="Product", entity_id=str(product.id),
        metadata={"snapshot": {"code": product.code, "name": product.name, "description": product.description, "status": product.status}},
    )
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
    # documented way to move a Product out of DRAFT at all. Optional and
    # backward-compatible: omitted, behaviour is unchanged.
    #
    # DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): editing name/description
    # no longer rolls a ProductVersion forward — there is nothing to roll.
    # The Product row is simply updated in place; its Plans are untouched
    # and immediately reflect the new Product name/description on their
    # next read (they reference the Product directly now).
    before = {"name": product.name, "description": product.description, "status": product.status}
    fields = {"name": name, "description": description, "row_version": row_version + 1}
    if status is not None:
        fields["status"] = status
    updated = Product.objects.filter(id=product.id, row_version=row_version).update(**fields)
    if updated == 0:
        raise RowVersionMismatchError(
            f"A versão do produto {product.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
        )
    product.refresh_from_db()
    after = {"name": product.name, "description": product.description, "status": product.status}
    changes = {
        key: {"from": before[key], "to": after[key]}
        for key in before
        if before[key] != after[key]
    }
    _audit.record(
        action="product.updated",
        entity_type="Product",
        entity_id=str(product.id),
        metadata={"rowVersion": product.row_version, "changes": changes},
    )
    return product


def delete_product(*, product: Product) -> None:
    """Cascades through every Plan/PlanBenefit the Product owns.

    Still fail-safe underneath: `quote`, `pricing_run` and
    `eligibility_evaluation` all hold a plain (non-CASCADE) foreign key to
    `plan` (see their own `0001_*_baseline.py` migrations) - if any of
    those already reference a Plan this product owns, Postgres raises
    IntegrityError, the whole delete rolls back untouched, and this
    surfaces as a 409 instead of a raw 500 (OD-ANGOLA-004: a Quote that
    already exists must never be silently orphaned or corrupted).
    `select_for_update()` on the Product also closes the same
    create_plan()-vs-this race as everywhere else.
    """
    try:
        with transaction.atomic():
            locked_product = Product.objects.select_for_update().get(id=product.id)
            plan_ids = list(Plan.objects.filter(product=locked_product).values_list("id", flat=True))
            PlanBenefit.objects.filter(plan_id__in=plan_ids).delete()
            Plan.objects.filter(id__in=plan_ids).delete()
            Product.objects.filter(id=locked_product.id).delete()
    except IntegrityError as exc:
        raise ImmutableVersionError(
            f"O produto {product.id} não pode ser eliminado: pelo menos um dos seus planos já é usado por uma cotação, cálculo ou avaliação de elegibilidade"
        ) from exc

    _audit.record(
        action="product.deleted", entity_type="Product", entity_id=str(product.id), metadata={"code": product.code}
    )


def _plan_signature(settings: dict | None) -> tuple:
    settings = settings or {}
    return (settings.get("segment"), settings.get("tier"), settings.get("category"))


def create_plan(
    *,
    product: Product,
    code: str,
    name: str,
    description: str | None,
    complementary_benefit_ids: list[uuid.UUID] | None = None,
    settings: dict | None = None,
) -> Plan:
    tenant_id = CurrentTenantProvider.require().value
    plan_settings, _warnings = validate_plan_settings(settings)
    # Resolved *before* the locked transaction below: a bad id here must
    # 400 (InvalidBenefitSelectionError) without ever touching a row lock.
    complementary_benefits = resolve_complementary_benefits(
        tenant_id=tenant_id, benefit_ids=complementary_benefit_ids or []
    )
    candidate_coverage_ids = core_benefit_ids(tenant_id) | {b.id for b in complementary_benefits}

    # `select_for_update()` serialises concurrent create_plan() calls
    # against this product, which is what makes the duplicate-coverage-set
    # check below race-free (no DB constraint can express "no two rows
    # share the same computed set").
    try:
        with transaction.atomic():
            locked_product = Product.objects.select_for_update().get(id=product.id)

            # Product Owner requirement: a Plan's coverages are its only
            # real differentiator, so no two Plans of the same Product may
            # end up with the exact same coverage set - this also covers
            # "at most one basic plan" for free, since an empty
            # `complementary_benefit_ids` candidate set equals BASE
            # coverages only, same as any other existing basic plan's.
            # PDF "Coberturas e Capitais" (Saúde Grupo): the 2-3 professional
            # categories (Colaboradores/Quadros/Administração) share the same
            # coverages and differ only in capitals — so plans that declare a
            # different segment/tier/category are *not* duplicates.
            candidate_signature = _plan_signature(plan_settings)
            for existing_plan in Plan.objects.filter(product=locked_product):
                existing_ids = set(
                    PlanBenefit.objects.filter(plan=existing_plan).values_list("benefit_id", flat=True)
                )
                if existing_ids == candidate_coverage_ids and _plan_signature(existing_plan.settings_json) == candidate_signature:
                    raise DuplicatePlanCoverageSetError(
                        f"O plano '{existing_plan.code}' já tem exatamente este conjunto de coberturas no produto {locked_product.id}"
                    )

            plan = Plan.objects.create(
                tenant_id=tenant_id,
                product=locked_product,
                code=code,
                name=name,
                description=description,
                status=PlanStatus.ACTIVE.value,
                settings_json=plan_settings,
            )
    except IntegrityError as exc:
        raise DuplicateCodeError(f"O código de plano '{code}' já existe no produto {product.id}") from exc

    # ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1: every Plan always carries the
    # 3 market-mandatory (BASE) coverages — never something a caller opts
    # into, and never skippable, so it happens here rather than in the view.
    # (benefit_service.remove_plan_benefit refuses to ever detach one, so
    # this invariant holds for the Plan's whole lifetime with no further
    # check needed at any other transition.)
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
            "productId": str(product.id),
            "code": plan.code,
            "name": plan.name,
        },
    )
    return plan


def update_plan(
    *, plan: Plan, name: str, description: str | None, row_version: int, settings: dict | None = None
) -> Plan:
    """DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): a Plan can be edited
    at any time now (no more parent-version DRAFT gate) — what a Quote
    already contracted is protected by its own immutable content snapshot
    (apps.quote), never by locking the Plan itself. Coverages are edited
    separately (PlanBenefitListCreateView/PlanBenefitDetailView) - this
    only covers name/description, via the same optimistic-locking
    `rowVersion` pattern as update_product()."""
    fields: dict = {"name": name, "description": description, "row_version": row_version + 1}
    if settings is not None:
        # Plan-level PDF rules (segment, ages, group rules, A-E options...);
        # omitted = unchanged. See apps.product.domain.plan_settings.
        fields["settings_json"] = validate_plan_settings(settings)[0]
    updated = Plan.objects.filter(id=plan.id, row_version=row_version).update(**fields)
    if updated == 0:
        raise RowVersionMismatchError(
            f"A versão do plano {plan.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
        )
    plan.refresh_from_db()
    _audit.record(
        action="plan.updated", entity_type="Plan", entity_id=str(plan.id), metadata={"rowVersion": plan.row_version}
    )
    return plan


def delete_plan(*, plan: Plan) -> None:
    """`plan_benefit` has no `ON DELETE CASCADE` (0001_product_baseline.py),
    so attached benefits are deleted first. `quote`/`pricing_run`/
    `eligibility_evaluation` all hold a plain (non-CASCADE) FK to `plan`,
    so Postgres raises IntegrityError (surfaced as 409) if any of them
    already reference this Plan — same protection delete_product() relies
    on, now the only gate left (no more DRAFT-only restriction)."""
    try:
        with transaction.atomic():
            PlanBenefit.objects.filter(plan_id=plan.id).delete()
            Plan.objects.filter(id=plan.id).delete()
    except IntegrityError as exc:
        raise ImmutableVersionError(
            f"O plano {plan.id} não pode ser eliminado: já é usado por uma cotação, cálculo ou avaliação de elegibilidade"
        ) from exc
    _audit.record(action="plan.deleted", entity_type="Plan", entity_id=str(plan.id), metadata={"code": plan.code})
