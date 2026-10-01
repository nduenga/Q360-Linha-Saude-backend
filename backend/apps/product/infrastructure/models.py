"""ORM adapters for the product module's physical schema.

Source of truth: Q360-MVP-ART-005 s2 ("PRODUCT / PLAN / BENEFIT") and s3
("VERSIONED PRICING CONFIGURATION"), ported verbatim by Q360-MVP-ART-012
V004-V007 — see `infrastructure/migrations/0001_product_baseline.py`.

All models are `managed = False` for the same reason as
`apps.foundation.infrastructure.models` (DOC-000 s3 P-08): the physical
schema is owned exclusively by the ART-012 migration, never by
`makemigrations`. All models inherit `TenantScopedModel` (Q360-S1-04):
`.objects` is transparently filtered to the authenticated actor's tenant.

`Benefit` and `PlanBenefit` have models here (ART-005 requires the tables,
and the future pricing engine needs to read `plan_benefit.configuration_json`)
but deliberately have NO serializer/view/URL in `interfaces/` — ART-006 does
not define any HTTP surface for them. See OPEN_DECISIONS.md#S02-CONTRACT-001.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.product.domain.enums import (
    BenefitStatus,
    PlanStatus,
    PricingParameterValueType,
    ProductStatus,
    VersionedConfigStatus,
)


class Product(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=[(s.value, s.value) for s in ProductStatus], default=ProductStatus.DRAFT.value
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "product"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code} ({self.id})"


class ProductVersion(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    product = models.ForeignKey(
        Product, on_delete=models.DO_NOTHING, db_column="product_id", related_name="versions"
    )
    version_no = models.IntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in VersionedConfigStatus],
        default=VersionedConfigStatus.DRAFT.value,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.CharField(max_length=200, null=True, blank=True)
    checksum = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "product_version"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.product_id}#v{self.version_no}"


class Plan(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    # DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26): a Plan
    # belongs directly to a Product — there is no more ProductVersion in
    # between. `product_version` is kept only for pre-existing rows
    # (nullable, apps.product 0002_plan_direct_to_product); no code writes
    # it any more and it is never read for a decision.
    product = models.ForeignKey(Product, on_delete=models.DO_NOTHING, db_column="product_id", related_name="plans")
    product_version = models.ForeignKey(
        ProductVersion,
        on_delete=models.DO_NOTHING,
        db_column="product_version_id",
        related_name="plans_legacy",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=[(s.value, s.value) for s in PlanStatus], default=PlanStatus.ACTIVE.value
    )
    # PDF "Coberturas e Capitais": segmento, escalão, sistema de acesso,
    # idades, regras de grupo... — ver `apps.product.domain.plan_settings`.
    settings_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "plan"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code} ({self.id})"


class Benefit(TenantScopedModel):
    """No ART-006 HTTP surface — see module docstring."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    benefit_type = models.CharField(max_length=60, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=[(s.value, s.value) for s in BenefitStatus], default=BenefitStatus.ACTIVE.value
    )
    definition_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "benefit"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code} ({self.id})"


class BenefitRevision(TenantScopedModel):
    """Immutable history row: one per change to a `Benefit` (create, update,
    deactivate, reactivate, rollback). `snapshot_json` is the full editable
    state *after* the change, so any revision can be restored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    benefit = models.ForeignKey(
        Benefit, on_delete=models.DO_NOTHING, db_column="benefit_id", related_name="revisions"
    )
    revision_no = models.IntegerField()
    action = models.CharField(max_length=40)
    snapshot_json = models.JSONField()
    reason = models.TextField(null=True, blank=True)
    changed_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "benefit_revision"


class PlanBenefit(TenantScopedModel):
    """No ART-006 HTTP surface — see module docstring."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id", related_name="plan_benefits")
    benefit = models.ForeignKey(Benefit, on_delete=models.DO_NOTHING, db_column="benefit_id")
    configuration_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "plan_benefit"


class PricingParameterSet(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=80)
    version_no = models.IntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in VersionedConfigStatus],
        default=VersionedConfigStatus.DRAFT.value,
    )
    checksum = models.CharField(max_length=128, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "pricing_parameter_set"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code}#v{self.version_no}"


class PricingParameter(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    parameter_set = models.ForeignKey(
        PricingParameterSet,
        on_delete=models.DO_NOTHING,
        db_column="parameter_set_id",
        related_name="parameters",
    )
    parameter_code = models.CharField(max_length=100)
    value_type = models.CharField(max_length=20, choices=[(t.value, t.value) for t in PricingParameterValueType])
    decimal_value = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    integer_value = models.BigIntegerField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    text_value = models.TextField(null=True, blank=True)
    json_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "pricing_parameter"
