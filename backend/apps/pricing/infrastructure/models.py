"""ORM adapters for the pricing module's physical schema (Q360-S4-01).

Source of truth: Q360-MVP-ART-005 s3 ("VERSIONED PRICING CONFIGURATION"),
ported verbatim by Q360-MVP-ART-012 V011 — see
`infrastructure/migrations/0001_pricing_baseline.py`. `managed = False` for
the same reason as every other module (DOC-000 s3 P-08). Inherits
`TenantScopedModel` (Q360-S1-04).
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.pricing.domain.enums import VersionedConfigStatus


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
