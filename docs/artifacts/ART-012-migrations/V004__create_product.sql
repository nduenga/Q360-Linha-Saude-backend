-- Q360-MVP-ART-012 — Flyway Migration V004
-- File: V004__create_product.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.product (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(60) NOT NULL,
    name                varchar(200) NOT NULL,
    description         text,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_product_code UNIQUE (tenant_id, code),
    CONSTRAINT ck_product_status CHECK (status IN ('DRAFT','ACTIVE','INACTIVE','ARCHIVED')),
    CONSTRAINT ck_product_row_version CHECK (row_version >= 0)
);
