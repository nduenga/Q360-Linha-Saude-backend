"""ORM adapters for the quote module's physical schema (Q360-S6-01..04).

Source of truth: Q360-MVP-ART-005 ("QUOTATION"), ported verbatim by
Q360-MVP-ART-012 V019-V021 — see `infrastructure/migrations/0001_quote_baseline.py`.
`managed = False` for the same reason as every other module (DOC-000 s3
P-08). Inherits `TenantScopedModel` (Q360-S1-04).

References `Proposer`/`InsuredMember` (apps.client), `ProductVersion`/`Plan`
(apps.product), `PricingRun` (apps.pricing) and `EligibilityEvaluation`
(apps.eligibility) directly — same pre-existing cross-module read pattern
as apps.eligibility/apps.pricing, see OPEN_DECISIONS.md#S04-CROSS-MODULE-001.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.infrastructure.models import EligibilityEvaluation
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.pricing.infrastructure.models import PricingRun
from apps.product.infrastructure.models import Plan, ProductVersion
from apps.quote.domain.enums import QuoteMemberStatus, QuoteSnapshotType, QuoteStatus


class Quote(TenantScopedModel):
    STATUS_CHOICES = [(s.value, s.value) for s in QuoteStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote_number = models.CharField(max_length=100, null=True, blank=True)
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    product_version = models.ForeignKey(ProductVersion, on_delete=models.DO_NOTHING, db_column="product_version_id")
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=QuoteStatus.DRAFT.value)
    effective_date = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, null=True, blank=True)
    latest_pricing_run = models.ForeignKey(
        PricingRun, on_delete=models.DO_NOTHING, db_column="latest_pricing_run_id", null=True, blank=True
    )
    submitted_by = models.CharField(max_length=200, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=200, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.CharField(max_length=200, null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "quote"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"Quote({self.id}, {self.status})"


class QuoteMember(TenantScopedModel):
    STATUS_CHOICES = [(s.value, s.value) for s in QuoteMemberStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, db_column="quote_id", related_name="members")
    member = models.ForeignKey(InsuredMember, on_delete=models.DO_NOTHING, db_column="member_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=QuoteMemberStatus.INCLUDED.value)
    eligibility_evaluation = models.ForeignKey(
        EligibilityEvaluation,
        on_delete=models.DO_NOTHING,
        db_column="eligibility_evaluation_id",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "quote_member"


class QuoteSnapshot(TenantScopedModel):
    TYPE_CHOICES = [(t.value, t.value) for t in QuoteSnapshotType]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.DO_NOTHING, db_column="quote_id", related_name="snapshots")
    snapshot_no = models.IntegerField()
    snapshot_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    pricing_run = models.ForeignKey(
        PricingRun, on_delete=models.DO_NOTHING, db_column="pricing_run_id", null=True, blank=True
    )
    product_version = models.ForeignKey(ProductVersion, on_delete=models.DO_NOTHING, db_column="product_version_id")
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    snapshot_json = models.JSONField()
    checksum = models.CharField(max_length=128)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "quote_snapshot"


class QuoteStateHistory(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.DO_NOTHING, db_column="quote_id", related_name="state_history")
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    reason_code = models.CharField(max_length=100, null=True, blank=True)
    reason_text = models.TextField(null=True, blank=True)
    changed_by = models.CharField(max_length=200)
    changed_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "quote_state_history"
