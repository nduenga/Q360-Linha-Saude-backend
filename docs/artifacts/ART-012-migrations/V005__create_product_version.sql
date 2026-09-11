-- Q360-MVP-ART-012 — Flyway Migration V005
-- File: V005__create_product_version.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.product_version (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    product_id          uuid NOT NULL REFERENCES q360.product(id),
    version_no          integer NOT NULL,
    effective_from      date NOT NULL,
    effective_to        date,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    published_at        timestamptz,
    published_by        varchar(200),
    checksum            varchar(128),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_product_version UNIQUE (tenant_id, product_id, version_no),
    CONSTRAINT ck_product_version_no CHECK (version_no > 0),
    CONSTRAINT ck_product_version_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_product_version_status CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
    CONSTRAINT ck_product_version_publish CHECK (
        (status = 'PUBLISHED' AND published_at IS NOT NULL)
        OR status <> 'PUBLISHED'
    ),
    CONSTRAINT ck_product_version_row_version CHECK (row_version >= 0)
);
CREATE INDEX ix_product_version_effective ON q360.product_version(tenant_id, product_id, effective_from, effective_to);
