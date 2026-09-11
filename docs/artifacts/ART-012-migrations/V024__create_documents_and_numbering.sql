-- Q360-MVP-ART-012 — Flyway Migration V024
-- File: V024__create_documents_and_numbering.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.document_template_version (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    template_code       varchar(80) NOT NULL,
    version_no          integer NOT NULL,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    storage_ref         text NOT NULL,
    checksum            varchar(128) NOT NULL,
    effective_from      date NOT NULL,
    effective_to        date,
    published_at        timestamptz,
    published_by        varchar(200),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_document_template UNIQUE (tenant_id, template_code, version_no),
    CONSTRAINT ck_template_version CHECK (version_no > 0),
    CONSTRAINT ck_template_status CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
    CONSTRAINT ck_template_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE q360.numbering_sequence (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    sequence_code       varchar(80) NOT NULL,
    period_key          varchar(40) NOT NULL,
    current_value       bigint NOT NULL DEFAULT 0,
    prefix              varchar(50),
    suffix              varchar(50),
    row_version         bigint NOT NULL DEFAULT 0,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_numbering_sequence UNIQUE (tenant_id, sequence_code, period_key),
    CONSTRAINT ck_numbering_value CHECK (current_value >= 0),
    CONSTRAINT ck_numbering_row_version CHECK (row_version >= 0)
);

CREATE TABLE q360.document (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id            uuid NOT NULL REFERENCES q360.quote(id),
    snapshot_id         uuid NOT NULL REFERENCES q360.quote_snapshot(id),
    template_version_id uuid NOT NULL REFERENCES q360.document_template_version(id),
    document_type       varchar(30) NOT NULL,
    document_number     varchar(100),
    status              varchar(20) NOT NULL DEFAULT 'REQUESTED',
    storage_ref         text,
    checksum            varchar(128),
    failure_code        varchar(100),
    requested_by        varchar(200) NOT NULL,
    requested_at        timestamptz NOT NULL DEFAULT now(),
    generated_at        timestamptz,
    CONSTRAINT ck_document_type CHECK (document_type IN ('QUOTE_PROPOSAL')),
    CONSTRAINT ck_document_status CHECK (status IN ('REQUESTED','GENERATED','FAILED')),
    CONSTRAINT ck_document_generated CHECK (
        (status='GENERATED' AND storage_ref IS NOT NULL AND checksum IS NOT NULL AND generated_at IS NOT NULL)
        OR status <> 'GENERATED'
    )
);
CREATE UNIQUE INDEX uq_document_number ON q360.document(tenant_id, document_number) WHERE document_number IS NOT NULL;
CREATE INDEX ix_document_quote ON q360.document(tenant_id, quote_id, requested_at DESC);

-- ============================================================
-- 10. INTEGRATION / OUTBOX / IDEMPOTENCY
-- ============================================================
