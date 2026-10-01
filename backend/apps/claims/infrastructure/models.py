"""Modelos da sinistralidade (R2) — ver `migrations/0001_claims_baseline.py`.
`managed = False`: o esquema pertence à migração (mesma regra de todos os
módulos). Dados de saúde: nada identifica o beneficiário além de uma
referência pseudonimizada escolhida por quem importa."""
from __future__ import annotations

import uuid

from django.db import models

from apps.client.infrastructure.models import Proposer
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel


class ClaimsImport(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    kind = models.CharField(max_length=10)
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    policy_id = models.UUIDField(null=True, blank=True)
    source = models.CharField(max_length=40, default="INTERNAL")
    file_name = models.CharField(max_length=250)
    total_rows = models.IntegerField()
    imported_rows = models.IntegerField()
    error_rows = models.IntegerField()
    errors_json = models.JSONField(default=list)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "claims_import"


class ClaimRecord(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    import_job = models.ForeignKey(ClaimsImport, on_delete=models.CASCADE, db_column="import_id", related_name="claims")
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    policy_id = models.UUIDField(null=True, blank=True)
    member_reference = models.CharField(max_length=100, null=True, blank=True)
    occurrence_date = models.DateField()
    benefit_code = models.CharField(max_length=60)
    paid_amount = models.DecimalField(max_digits=30, decimal_places=8)
    provision_amount = models.DecimalField(max_digits=30, decimal_places=8, default=0)
    currency_code = models.CharField(max_length=3)
    status = models.CharField(max_length=20, default="PAID")

    class Meta:
        managed = False
        db_table = "claim_record"


class PremiumRecord(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    import_job = models.ForeignKey(ClaimsImport, on_delete=models.CASCADE, db_column="import_id", related_name="premiums")
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    policy_id = models.UUIDField(null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    premium_amount = models.DecimalField(max_digits=30, decimal_places=8)
    insured_count = models.IntegerField(null=True, blank=True)
    currency_code = models.CharField(max_length=3)

    class Meta:
        managed = False
        db_table = "premium_record"


class ProjectionAssumptionSet(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    name = models.CharField(max_length=200)
    params_json = models.JSONField()
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "projection_assumption_set"


class ProjectionRun(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    policy_id = models.UUIDField(null=True, blank=True)
    assumption_set = models.ForeignKey(
        ProjectionAssumptionSet, on_delete=models.SET_NULL, db_column="assumption_set_id", null=True, blank=True
    )
    params_json = models.JSONField()
    result_json = models.JSONField()
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "projection_run"
