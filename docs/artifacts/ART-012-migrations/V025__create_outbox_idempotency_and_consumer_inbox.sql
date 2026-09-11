-- Q360-MVP-ART-012 — Flyway Migration V025
-- File: V025__create_outbox_idempotency_and_consumer_inbox.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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
    CONSTRAINT ck_outbox_schema_version CHECK (schema_version > 0),
    CONSTRAINT ck_outbox_payload_object CHECK (jsonb_typeof(payload_json) = 'object'),
    CONSTRAINT ck_outbox_status CHECK (status IN ('PENDING','PROCESSING','PUBLISHED','FAILED')),
    CONSTRAINT ck_outbox_attempts CHECK (attempts >= 0)
);
CREATE INDEX ix_outbox_dispatch ON q360.outbox_event(status, next_attempt_at, occurred_at)
WHERE status IN ('PENDING','FAILED');
CREATE INDEX ix_outbox_aggregate ON q360.outbox_event(tenant_id, aggregate_type, aggregate_id, occurred_at);

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
    CONSTRAINT uq_idempotency UNIQUE (tenant_id, operation_code, idempotency_key),
    CONSTRAINT ck_idempotency_status CHECK (status IN ('IN_PROGRESS','COMPLETED','FAILED')),
    CONSTRAINT ck_idempotency_expiry CHECK (expires_at > created_at)
);
CREATE INDEX ix_idempotency_expiry ON q360.idempotency_record(expires_at);

-- ART-007 refinement: dedicated consumer inbox.
CREATE TABLE q360.consumer_inbox (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES q360.tenant(id), event_id uuid NOT NULL,
 consumer_name varchar(150) NOT NULL, event_type varchar(150) NOT NULL, schema_version integer NOT NULL,
 payload_checksum varchar(128), processed_at timestamptz NOT NULL DEFAULT now(), correlation_id varchar(100),
 CONSTRAINT uq_consumer_inbox_event UNIQUE (tenant_id, consumer_name, event_id),
 CONSTRAINT ck_consumer_inbox_schema_version CHECK (schema_version >= 1)
);
CREATE INDEX ix_consumer_inbox_processed ON q360.consumer_inbox(tenant_id, consumer_name, processed_at DESC);
COMMENT ON TABLE q360.consumer_inbox IS 'ART-007 consumer idempotency inbox: one eventId once per consumer per tenant.';
