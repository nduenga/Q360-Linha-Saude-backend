-- Q360-MVP-ART-012 — Flyway Migration V022
-- File: V022__create_authority_and_review.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.authority_policy (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(80) NOT NULL,
    version_no          integer NOT NULL,
    effective_from      date NOT NULL,
    effective_to        date,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    policy_json         jsonb NOT NULL,
    checksum            varchar(128),
    published_at        timestamptz,
    published_by        varchar(200),
    approved_by         varchar(200),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_authority_policy UNIQUE (tenant_id, code, version_no),
    CONSTRAINT ck_authority_version CHECK (version_no > 0),
    CONSTRAINT ck_authority_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_authority_status CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
    CONSTRAINT ck_authority_policy_json CHECK (jsonb_typeof(policy_json) = 'object'),
    CONSTRAINT ck_authority_four_eyes CHECK (approved_by IS NULL OR published_by IS NULL OR approved_by <> published_by)
);

CREATE TABLE q360.review_task (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id            uuid NOT NULL REFERENCES q360.quote(id),
    status              varchar(20) NOT NULL DEFAULT 'OPEN',
    assigned_to         varchar(200),
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    started_at          timestamptz,
    decided_at          timestamptz,
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_review_status CHECK (status IN ('OPEN','IN_PROGRESS','DECIDED','RETURNED')),
    CONSTRAINT ck_review_row_version CHECK (row_version >= 0)
);
CREATE INDEX ix_review_queue ON q360.review_task(tenant_id, status, created_at);
