"""ORM adapters for the foundation module's physical schema.

Source of truth: Q360-MVP-ART-005 (DDL PostgreSQL) s1 (tenant/audit) and s.
"Drools/Rules integration" (`rule_set`/`rule_version`), ported verbatim by
Q360-MVP-ART-012 V002/V003 — see `infrastructure/migrations/0001_foundation_baseline.py`
— and V012/V013 — see `infrastructure/migrations/0002_rules_baseline.py`.

`RuleSet`/`RuleVersion` live here, not in a business module, because
DOC-004 s3.1's own dependency table would otherwise be unsatisfiable:
`eligibility` depends only on `foundation, product, client`, while
`pricing` depends on `foundation, product/eligibility` — i.e. pricing may
depend on eligibility, never the other way round. But `eligibility_evaluation`
(ART-005 s5) has a hard FK to `rule_version`, and DOC-004 s11 ("Drools /
Rules integration") itself is a section separate from s10 ("Pricing module
— núcleo"), with `rule_domain` spanning ELIGIBILITY/PRICING/WORKFLOW/VALIDATION
— i.e. it is cross-cutting, not pricing-owned. Placing it under `pricing`
would make eligibility depend on pricing, contradicting DOC-004's own
graph; foundation is the only module both `eligibility` and the future
`pricing` module can depend on without contradiction.

These models are declared `managed = False`: the physical schema (columns,
constraints, indexes) is owned exclusively by that migration. Django's
schema editor must never create/alter these tables, and `makemigrations`
must never be run against this app — doing so would let the ORM "invent" a
schema instead of following ART-005/ART-012 (DOC-000 s3 P-08: "Database
migration only"; golden rule against inventing structure).

Table names are intentionally unqualified (no `q360.` prefix): the `q360`
schema is resolved via `search_path=public,q360` configured in
`DATABASES["default"]["OPTIONS"]` (config/settings/base.py). `public` is
first so Django's own internal apps (contenttypes, auth) keep landing in
`public` and never collide with the q360 business schema.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default="ACTIVE")
    # Dados da empresa cliente (razão social, NIF, contactos, morada), geridos
    # pela plataforma (apps.platform_admin).
    profile_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "tenant"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code} ({self.id})"


class AuditEvent(TenantScopedModel):
    ACTOR_TYPE_CHOICES = (
        ("USER", "USER"),
        ("SYSTEM", "SYSTEM"),
        ("SERVICE", "SERVICE"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.DO_NOTHING,
        db_column="tenant_id",
        related_name="audit_events",
    )
    actor_id = models.CharField(max_length=200, null=True, blank=True)
    actor_type = models.CharField(max_length=30, choices=ACTOR_TYPE_CHOICES, default="USER")
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=120)
    entity_id = models.CharField(max_length=200, null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)
    trace_id = models.CharField(max_length=100, null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)
    metadata_json = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = "audit_event"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.action} {self.entity_type}:{self.entity_id}"


class RuleSet(TenantScopedModel):
    RULE_DOMAIN_CHOICES = (
        ("ELIGIBILITY", "ELIGIBILITY"),
        ("PRICING", "PRICING"),
        ("WORKFLOW", "WORKFLOW"),
        ("VALIDATION", "VALIDATION"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    rule_domain = models.CharField(max_length=40, choices=RULE_DOMAIN_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "rule_set"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.code} ({self.rule_domain})"


class RuleVersion(TenantScopedModel):
    STATUS_CHOICES = (("DRAFT", "DRAFT"), ("PUBLISHED", "PUBLISHED"), ("RETIRED", "RETIRED"))
    ARTIFACT_TYPE_CHOICES = (
        ("DRL", "DRL"),
        ("DECISION_TABLE", "DECISION_TABLE"),
        ("JSON", "JSON"),
        ("INTERNAL", "INTERNAL"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    rule_set = models.ForeignKey(RuleSet, on_delete=models.DO_NOTHING, db_column="rule_set_id", related_name="versions")
    version_no = models.IntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    artifact_type = models.CharField(max_length=30, choices=ARTIFACT_TYPE_CHOICES, default="DECISION_TABLE")
    artifact_ref = models.TextField(null=True, blank=True)
    artifact_checksum = models.CharField(max_length=128, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.CharField(max_length=200, null=True, blank=True)
    approved_by = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "rule_version"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.rule_set_id}#v{self.version_no}"


class OutboxEvent(TenantScopedModel):
    STATUS_CHOICES = (
        ("PENDING", "PENDING"),
        ("PROCESSING", "PROCESSING"),
        ("PUBLISHED", "PUBLISHED"),
        ("FAILED", "FAILED"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id", related_name="outbox_events")
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=150)
    schema_version = models.IntegerField(default=1)
    payload_json = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)
    causation_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    attempts = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=120, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    last_error_safe = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "outbox_event"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.event_type} {self.aggregate_type}:{self.aggregate_id}"


class IdempotencyRecord(TenantScopedModel):
    STATUS_CHOICES = (
        ("IN_PROGRESS", "IN_PROGRESS"),
        ("COMPLETED", "COMPLETED"),
        ("FAILED", "FAILED"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id", related_name="idempotency_records")
    idempotency_key = models.CharField(max_length=200)
    operation_code = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="IN_PROGRESS")
    response_status = models.IntegerField(null=True, blank=True)
    response_body_json = models.JSONField(null=True, blank=True)
    resource_id = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "idempotency_record"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.operation_code}:{self.idempotency_key}"


class ConsumerInbox(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id", related_name="consumer_inbox")
    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=150)
    event_type = models.CharField(max_length=150)
    schema_version = models.IntegerField()
    payload_checksum = models.CharField(max_length=128, null=True, blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "consumer_inbox"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.consumer_name}:{self.event_id}"


class SystemParameter(TenantScopedModel):
    """Valor atual de um parâmetro global (as definições vivem em
    `apps.foundation.domain.system_parameters`; sem linha = valor por omissão)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=100)
    value_json = models.JSONField()
    updated_by = models.CharField(max_length=200)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "system_parameter"


class SystemParameterRevision(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=100)
    revision_no = models.IntegerField()
    action = models.CharField(max_length=30)
    value_json = models.JSONField()
    reason = models.TextField(null=True, blank=True)
    changed_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "system_parameter_revision"
