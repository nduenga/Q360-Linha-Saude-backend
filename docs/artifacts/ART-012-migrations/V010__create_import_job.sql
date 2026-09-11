-- Q360-MVP-ART-012 — Flyway Migration V010
-- File: V010__create_import_job.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.import_job (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id         uuid REFERENCES q360.proposer(id),
    import_type         varchar(30) NOT NULL,
    original_filename   varchar(255),
    file_checksum       varchar(128),
    status              varchar(20) NOT NULL DEFAULT 'UPLOADED',
    total_rows          integer NOT NULL DEFAULT 0,
    valid_rows          integer NOT NULL DEFAULT 0,
    invalid_rows        integer NOT NULL DEFAULT 0,
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    CONSTRAINT ck_import_type CHECK (import_type IN ('MEMBER_POPULATION')),
    CONSTRAINT ck_import_status CHECK (status IN ('UPLOADED','VALIDATING','VALIDATED','COMMITTING','COMPLETED','FAILED')),
    CONSTRAINT ck_import_counts CHECK (total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0)
);

CREATE TABLE q360.import_row_error (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    import_job_id       uuid NOT NULL REFERENCES q360.import_job(id) ON DELETE CASCADE,
    row_number          integer NOT NULL,
    field_name          varchar(120),
    error_code          varchar(80) NOT NULL,
    error_message       text NOT NULL,
    raw_value_masked    text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_import_row_number CHECK (row_number > 0)
);
CREATE INDEX ix_import_error_job ON q360.import_row_error(tenant_id, import_job_id, row_number);

-- ============================================================
-- 5. ELIGIBILITY
-- ============================================================
