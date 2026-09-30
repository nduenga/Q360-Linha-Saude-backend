"""ORM adapters for the client module's physical schema.

Source of truth: Q360-MVP-ART-005 s4 ("CLIENT / POPULATION"), ported
verbatim by Q360-MVP-ART-012 V008-V010 — see
`infrastructure/migrations/0001_client_baseline.py`. `managed = False` for
the same reason as every other module (DOC-000 s3 P-08). All models
inherit `TenantScopedModel` (Q360-S1-04).
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.client.domain.enums import (
    ImportJobStatus,
    ImportType,
    MemberStatus,
    ProposerStatus,
    ProposerType,
    RelationshipCategory,
)


class Proposer(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    proposer_type = models.CharField(max_length=20, choices=[(t.value, t.value) for t in ProposerType])
    external_reference = models.CharField(max_length=100, null=True, blank=True)
    display_name = models.CharField(max_length=250)
    nif = models.CharField(max_length=14, null=True, blank=True)
    registration_number = models.CharField(max_length=100, null=True, blank=True)
    email = models.CharField(max_length=254, null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    attributes_json = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=[(s.value, s.value) for s in ProposerStatus], default=ProposerStatus.ACTIVE.value
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "proposer"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.display_name} ({self.id})"


class InsuredMember(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    proposer = models.ForeignKey(
        Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id", related_name="members"
    )
    external_reference = models.CharField(max_length=100, null=True, blank=True)
    relationship_code = models.CharField(max_length=40)
    first_name = models.CharField(max_length=120, null=True, blank=True)
    last_name = models.CharField(max_length=120, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    sex_code = models.CharField(max_length=20, null=True, blank=True)
    attributes_json = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=[(s.value, s.value) for s in MemberStatus], default=MemberStatus.ACTIVE.value
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "insured_member"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.first_name or ''} {self.last_name or ''} ({self.id})".strip()


class RelationshipCode(TenantScopedModel):
    """OD-003 (ROADMAP_ANGOLA_CUSTOMIZATION.md, OPEN_DECISIONS.md
    #S03-RELATIONSHIP-001) — pragmatic V1 addition, not ART-005/ART-012.
    See apps/client/infrastructure/migrations/0002_relationship_catalog.py."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=40)
    label = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=[(c.value, c.value) for c in RelationshipCategory])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "relationship_code"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code} ({self.label})"


class ImportJob(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    proposer = models.ForeignKey(
        Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id", null=True, blank=True, related_name="import_jobs"
    )
    import_type = models.CharField(max_length=30, choices=[(t.value, t.value) for t in ImportType])
    original_filename = models.CharField(max_length=255, null=True, blank=True)
    file_checksum = models.CharField(max_length=128, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=[(s.value, s.value) for s in ImportJobStatus], default=ImportJobStatus.UPLOADED.value
    )
    total_rows = models.IntegerField(default=0)
    valid_rows = models.IntegerField(default=0)
    invalid_rows = models.IntegerField(default=0)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "import_job"


class ImportRowError(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    import_job = models.ForeignKey(
        ImportJob, on_delete=models.DO_NOTHING, db_column="import_job_id", related_name="row_errors"
    )
    row_number = models.IntegerField()
    field_name = models.CharField(max_length=120, null=True, blank=True)
    error_code = models.CharField(max_length=80)
    error_message = models.TextField()
    raw_value_masked = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "import_row_error"
