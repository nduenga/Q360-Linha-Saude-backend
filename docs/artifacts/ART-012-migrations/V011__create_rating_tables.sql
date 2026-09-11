-- Q360-MVP-ART-012 — Flyway Migration V011
-- File: V011__create_rating_tables.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.rating_table (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(80) NOT NULL,
    name                varchar(200) NOT NULL,
    version_no          integer NOT NULL,
    effective_from      date NOT NULL,
    effective_to        date,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    currency_code       char(3),
    checksum            varchar(128),
    published_at        timestamptz,
    published_by        varchar(200),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_rating_table UNIQUE (tenant_id, code, version_no),
    CONSTRAINT ck_rating_version CHECK (version_no > 0),
    CONSTRAINT ck_rating_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_rating_status CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
    CONSTRAINT ck_rating_currency CHECK (currency_code IS NULL OR currency_code ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_rating_row_version CHECK (row_version >= 0)
);

CREATE TABLE q360.rating_factor (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    rating_table_id     uuid NOT NULL REFERENCES q360.rating_table(id),
    factor_code         varchar(100) NOT NULL,
    dimension_json      jsonb NOT NULL DEFAULT '{}'::jsonb,
    factor_value        numeric(30,12) NOT NULL,
    priority            integer NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_rating_factor_dimension CHECK (jsonb_typeof(dimension_json) = 'object')
);
CREATE INDEX ix_rating_factor_lookup ON q360.rating_factor(tenant_id, rating_table_id, factor_code, priority DESC);
CREATE INDEX ix_rating_factor_dimension_gin ON q360.rating_factor USING gin(dimension_json);
