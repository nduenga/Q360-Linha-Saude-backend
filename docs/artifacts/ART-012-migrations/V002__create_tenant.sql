-- Q360-MVP-ART-012 — Flyway Migration V002
-- File: V002__create_tenant.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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
