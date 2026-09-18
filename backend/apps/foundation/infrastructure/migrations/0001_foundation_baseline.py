"""Foundation baseline schema (Q360-S1-02, Q360-S1-05).

Ports Q360-MVP-ART-012 V001, V002 and V003 verbatim via `RunSQL`. This is
the ONLY place allowed to create/alter `q360.tenant` and `q360.audit_event`
— do not edit the SQL below without first updating the ART-012 source of
truth (docs/artifacts/ART-012-migrations/) and recording a Change Request
(DOC-000 s12). See infrastructure/models.py for why the matching Django
models are declared `managed = False`.

Rollback follows the ART-012 README policy: forward-only. `reverse_sql` is
a deliberate no-op (not a real DOWN migration) — `migrate foundation zero`
will not resurrect a working state; that must go through the approved
backup/restore procedure.
"""
from django.db import migrations

V001_CREATE_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS q360;
"""

V002_CREATE_TENANT = """
CREATE TABLE q360.tenant (
    id                  uuid PRIMARY KEY,
    code                varchar(50) NOT NULL,
    name                varchar(200) NOT NULL,
    status              varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_tenant_code UNIQUE (code),
    CONSTRAINT ck_tenant_status CHECK (status IN ('ACTIVE','SUSPENDED','INACTIVE')),
    CONSTRAINT ck_tenant_row_version CHECK (row_version >= 0)
);
"""

V003_CREATE_AUDIT_EVENT = """
CREATE TABLE q360.audit_event (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    actor_id            varchar(200),
    actor_type          varchar(30) NOT NULL DEFAULT 'USER',
    action              varchar(120) NOT NULL,
    entity_type         varchar(120) NOT NULL,
    entity_id           varchar(200),
    occurred_at         timestamptz NOT NULL DEFAULT now(),
    correlation_id      varchar(100),
    trace_id            varchar(100),
    source              varchar(100),
    metadata_json       jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_audit_actor_type CHECK (actor_type IN ('USER','SYSTEM','SERVICE')),
    CONSTRAINT ck_audit_metadata_object CHECK (jsonb_typeof(metadata_json) = 'object')
);
CREATE INDEX ix_audit_tenant_occurred ON q360.audit_event(tenant_id, occurred_at DESC);
CREATE INDEX ix_audit_entity ON q360.audit_event(tenant_id, entity_type, entity_id);
CREATE INDEX ix_audit_correlation ON q360.audit_event(correlation_id) WHERE correlation_id IS NOT NULL;
"""

V004_CREATE_OUTBOX_EVENT = """
CREATE TABLE q360.outbox_event (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    aggregate_type      varchar(100) NOT NULL,
    aggregate_id        varchar(200) NOT NULL,
    event_type          varchar(150) NOT NULL,
    schema_version      integer NOT NULL DEFAULT 1,
    payload_json        jsonb NOT NULL,
    occurred_at         timestamptz NOT NULL DEFAULT now(),
    correlation_id      varchar(100),
    causation_id        varchar(100),
    status              varchar(20) NOT NULL DEFAULT 'PENDING',
    attempts            integer NOT NULL DEFAULT 0,
    next_attempt_at     timestamptz,
    locked_at           timestamptz,
    locked_by           varchar(120),
    published_at        timestamptz,
    last_error_safe     text,
    CONSTRAINT ck_outbox_status CHECK (status IN ('PENDING','PROCESSING','PUBLISHED','FAILED')),
    CONSTRAINT ck_outbox_schema_version CHECK (schema_version >= 1),
    CONSTRAINT ck_outbox_attempts CHECK (attempts >= 0),
    CONSTRAINT ck_outbox_payload_object CHECK (jsonb_typeof(payload_json) = 'object')
);
CREATE INDEX ix_outbox_pending ON q360.outbox_event(tenant_id, status, next_attempt_at);
CREATE INDEX ix_outbox_aggregate ON q360.outbox_event(tenant_id, aggregate_type, aggregate_id);
CREATE INDEX ix_outbox_correlation ON q360.outbox_event(correlation_id) WHERE correlation_id IS NOT NULL;
"""

V005_CREATE_IDEMPOTENCY_RECORD = """
CREATE TABLE q360.idempotency_record (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    idempotency_key     varchar(200) NOT NULL,
    operation_code      varchar(120) NOT NULL,
    request_hash        varchar(128) NOT NULL,
    status              varchar(20) NOT NULL DEFAULT 'IN_PROGRESS',
    response_status     integer,
    response_body_json  jsonb,
    resource_id         varchar(200),
    created_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    expires_at          timestamptz NOT NULL,
    CONSTRAINT uq_idempotency_key UNIQUE (tenant_id, idempotency_key, operation_code),
    CONSTRAINT ck_idempotency_status CHECK (status IN ('IN_PROGRESS','COMPLETED','FAILED')),
    CONSTRAINT ck_idempotency_request_hash CHECK (length(request_hash) > 0)
);
CREATE INDEX ix_idempotency_tenant_expires ON q360.idempotency_record(tenant_id, expires_at);
"""

V006_CREATE_CONSUMER_INBOX = """
CREATE TABLE q360.consumer_inbox (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    event_id            uuid NOT NULL,
    consumer_name       varchar(150) NOT NULL,
    event_type          varchar(150) NOT NULL,
    schema_version      integer NOT NULL,
    payload_checksum    varchar(128),
    processed_at        timestamptz NOT NULL DEFAULT now(),
    correlation_id      varchar(100),
    CONSTRAINT uq_consumer_inbox UNIQUE (tenant_id, consumer_name, event_id),
    CONSTRAINT ck_consumer_inbox_schema_version CHECK (schema_version >= 1)
);
CREATE INDEX ix_consumer_inbox_tenant_processed ON q360.consumer_inbox(tenant_id, processed_at DESC);
"""


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []
    operations = [
        migrations.RunSQL(sql=V001_CREATE_SCHEMA, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V002_CREATE_TENANT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V003_CREATE_AUDIT_EVENT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V004_CREATE_OUTBOX_EVENT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V005_CREATE_IDEMPOTENCY_RECORD, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V006_CREATE_CONSUMER_INBOX, reverse_sql=migrations.RunSQL.noop),
    ]
