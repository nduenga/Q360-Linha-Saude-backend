"""ORM adapters for the pricing module's physical schema (Q360-S4-01,
S4-02, S4-04, S5-02).

Source of truth: Q360-MVP-ART-005 s3 ("VERSIONED PRICING CONFIGURATION"),
ported verbatim by Q360-MVP-ART-012 V011 (RatingTable/RatingFactor) and
V015-V018 (PricingRun/PricingComponent/PricingTrace/PricingScenario) — see
`infrastructure/migrations/`. `managed = False` for the same reason as
every other module (DOC-000 s3 P-08). Inherits `TenantScopedModel`
(Q360-S1-04).

`PricingRun`/`PricingComponent` reference `ProductVersion`/`Plan`
(apps.product) and `InsuredMember` (apps.client) directly, same as
`apps.eligibility.application.use_cases` already does for the same
entities — see OPEN_DECISIONS.md#S04-CROSS-MODULE-001 for why this is a
flagged, pre-existing pattern rather than a new one.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.client.infrastructure.models import InsuredMember
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.pricing.domain.enums import PricingComponentType, PricingRunStatus, VersionedConfigStatus
from apps.product.infrastructure.models import Plan, PricingParameterSet, ProductVersion


class RatingTable(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version_no = models.IntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=[(s.value, s.value) for s in VersionedConfigStatus], default=VersionedConfigStatus.DRAFT.value
    )
    currency_code = models.CharField(max_length=3, null=True, blank=True)
    checksum = models.CharField(max_length=128, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "rating_table"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code}#v{self.version_no}"


class RatingFactor(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    rating_table = models.ForeignKey(
        RatingTable, on_delete=models.DO_NOTHING, db_column="rating_table_id", related_name="factors"
    )
    factor_code = models.CharField(max_length=100)
    dimension_json = models.JSONField(default=dict)
    factor_value = models.DecimalField(max_digits=30, decimal_places=12)
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "rating_factor"


class PricingRun(TenantScopedModel):
    STATUS_CHOICES = [(s.value, s.value) for s in PricingRunStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    product_version = models.ForeignKey(ProductVersion, on_delete=models.DO_NOTHING, db_column="product_version_id")
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    rating_table = models.ForeignKey(RatingTable, on_delete=models.DO_NOTHING, db_column="rating_table_id")
    parameter_set = models.ForeignKey(
        PricingParameterSet, on_delete=models.DO_NOTHING, db_column="parameter_set_id"
    )
    rule_version = models.ForeignKey(
        RuleVersion, on_delete=models.DO_NOTHING, db_column="rule_version_id", null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PricingRunStatus.REQUESTED.value)
    effective_date = models.DateField()
    currency_code = models.CharField(max_length=3)
    rounding_policy_code = models.CharField(max_length=80)
    rounding_policy_version = models.IntegerField()
    input_snapshot_json = models.JSONField()
    total_amount = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=100, null=True, blank=True)
    failure_message_safe = models.TextField(null=True, blank=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "pricing_run"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"PricingRun({self.id}, {self.status})"


class PricingComponent(TenantScopedModel):
    TYPE_CHOICES = [(t.value, t.value) for t in PricingComponentType]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    pricing_run = models.ForeignKey(
        PricingRun, on_delete=models.CASCADE, db_column="pricing_run_id", related_name="components"
    )
    member = models.ForeignKey(
        InsuredMember, on_delete=models.DO_NOTHING, db_column="member_id", null=True, blank=True
    )
    component_order = models.IntegerField()
    component_code = models.CharField(max_length=100)
    component_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    base_amount = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    factor_value = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    adjustment_amount = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    result_amount = models.DecimalField(max_digits=30, decimal_places=8)
    source_code = models.CharField(max_length=120, null=True, blank=True)
    source_version = models.CharField(max_length=80, null=True, blank=True)
    metadata_json = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = "pricing_component"


class PricingTrace(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    pricing_run = models.ForeignKey(
        PricingRun, on_delete=models.CASCADE, db_column="pricing_run_id", related_name="trace_steps"
    )
    sequence_no = models.IntegerField()
    step_code = models.CharField(max_length=100)
    rule_code = models.CharField(max_length=120, null=True, blank=True)
    input_json = models.JSONField(null=True, blank=True)
    output_json = models.JSONField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "pricing_trace"


class PricingScenario(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    base_pricing_run = models.ForeignKey(
        PricingRun,
        on_delete=models.DO_NOTHING,
        db_column="base_pricing_run_id",
        null=True,
        blank=True,
        related_name="+",
    )
    name = models.CharField(max_length=200)
    input_override_json = models.JSONField(default=dict)
    result_pricing_run = models.ForeignKey(
        PricingRun,
        on_delete=models.DO_NOTHING,
        db_column="result_pricing_run_id",
        null=True,
        blank=True,
        related_name="+",
    )
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "pricing_scenario"
