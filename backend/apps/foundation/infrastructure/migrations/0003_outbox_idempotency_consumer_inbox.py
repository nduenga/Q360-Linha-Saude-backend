"""Transactional Outbox / Idempotency / Consumer Inbox (Q360-S09).

Ports Q360-MVP-ART-012 V025 verbatim via `RunSQL`. See
`0001_foundation_baseline.py` for the general verbatim-migration policy.

This DDL originally landed appended to `0001_foundation_baseline.py`
after that migration had already been applied in existing environments —
Django's migration runner tracks applied migrations by name, not content,
so editing an already-applied migration's SQL is silently never re-run
and the tables never get created anywhere the app was previously deployed
(only a brand-new database running every migration from scratch would
have them). Moved here as a proper new migration so `manage.py migrate`
picks it up everywhere.
"""
from django.db import migrations

V025_CREATE_OUTBOX_EVENT = """
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

V025_CREATE_IDEMPOTENCY_RECORD = """
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

V025_CREATE_CONSUMER_INBOX = """
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
    dependencies = [("foundation", "0002_rules_baseline")]
    operations = [
        migrations.RunSQL(sql=V025_CREATE_OUTBOX_EVENT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V025_CREATE_IDEMPOTENCY_RECORD, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V025_CREATE_CONSUMER_INBOX, reverse_sql=migrations.RunSQL.noop),
    ]
