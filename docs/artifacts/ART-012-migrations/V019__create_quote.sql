-- Q360-MVP-ART-012 — Flyway Migration V019
-- File: V019__create_quote.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.quote (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_number        varchar(100),
    proposer_id         uuid NOT NULL REFERENCES q360.proposer(id),
    product_version_id  uuid NOT NULL REFERENCES q360.product_version(id),
    plan_id             uuid NOT NULL REFERENCES q360.plan(id),
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    effective_date      date NOT NULL,
    valid_until         date,
    currency_code       char(3),
    latest_pricing_run_id uuid REFERENCES q360.pricing_run(id),
    submitted_by        varchar(200),
    submitted_at        timestamptz,
    approved_by         varchar(200),
    approved_at         timestamptz,
    rejected_by         varchar(200),
    rejected_at         timestamptz,
    cancellation_reason text,
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_quote_status CHECK (status IN ('DRAFT','READY','IN_REVIEW','APPROVED','REJECTED','EXPIRED','CANCELLED')),
    CONSTRAINT ck_quote_dates CHECK (valid_until IS NULL OR valid_until >= effective_date),
    CONSTRAINT ck_quote_currency CHECK (currency_code IS NULL OR currency_code ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_quote_four_eyes CHECK (approved_by IS NULL OR submitted_by IS NULL OR approved_by <> submitted_by),
    CONSTRAINT ck_quote_row_version CHECK (row_version >= 0)
);
CREATE UNIQUE INDEX uq_quote_number ON q360.quote(tenant_id, quote_number) WHERE quote_number IS NOT NULL;
CREATE INDEX ix_quote_proposer ON q360.quote(tenant_id, proposer_id, created_at DESC);
CREATE INDEX ix_quote_status ON q360.quote(tenant_id, status, updated_at DESC);
