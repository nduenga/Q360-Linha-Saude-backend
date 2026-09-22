"""ORM adapter for the eligibility module's physical schema.

Source of truth: Q360-MVP-ART-005 s5 ("ELIGIBILITY"), ported verbatim by
Q360-MVP-ART-012 V014 — see `infrastructure/migrations/0001_eligibility_baseline.py`.
`managed = False` for the same reason as every other module (DOC-000 s3
P-08). Inherits `TenantScopedModel` (Q360-S1-04).
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.domain.enums import EligibilityDecision
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.product.infrastructure.models import Plan, ProductVersion


class EligibilityEvaluation(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    proposer = models.ForeignKey(
        Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id", null=True, blank=True
    )
    member = models.ForeignKey(
        InsuredMember, on_delete=models.DO_NOTHING, db_column="member_id", null=True, blank=True
    )
    product_version = models.ForeignKey(ProductVersion, on_delete=models.DO_NOTHING, db_column="product_version_id")
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    rule_version = models.ForeignKey(
        RuleVersion, on_delete=models.DO_NOTHING, db_column="rule_version_id", null=True, blank=True
    )
    decision = models.CharField(max_length=30, choices=[(d.value, d.value) for d in EligibilityDecision])
    input_snapshot_json = models.JSONField()
    evidence_json = models.JSONField(default=list)
    evaluated_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "eligibility_evaluation"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.decision} ({self.id})"
