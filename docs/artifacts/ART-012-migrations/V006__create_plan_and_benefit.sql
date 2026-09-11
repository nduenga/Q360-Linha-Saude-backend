-- Q360-MVP-ART-012 — Flyway Migration V006
-- File: V006__create_plan_and_benefit.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.plan (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    product_version_id  uuid NOT NULL REFERENCES q360.product_version(id),
    code                varchar(60) NOT NULL,
    name                varchar(200) NOT NULL,
    description         text,
    status              varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_plan_code UNIQUE (tenant_id, product_version_id, code),
    CONSTRAINT ck_plan_status CHECK (status IN ('ACTIVE','INACTIVE')),
    CONSTRAINT ck_plan_row_version CHECK (row_version >= 0)
);

CREATE TABLE q360.benefit (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(60) NOT NULL,
    name                varchar(200) NOT NULL,
    benefit_type        varchar(60),
    description         text,
    status              varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_benefit_code UNIQUE (tenant_id, code),
    CONSTRAINT ck_benefit_status CHECK (status IN ('ACTIVE','INACTIVE')),
    CONSTRAINT ck_benefit_row_version CHECK (row_version >= 0)
);

CREATE TABLE q360.plan_benefit (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    plan_id             uuid NOT NULL REFERENCES q360.plan(id),
    benefit_id          uuid NOT NULL REFERENCES q360.benefit(id),
    configuration_json  jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_plan_benefit UNIQUE (tenant_id, plan_id, benefit_id),
    CONSTRAINT ck_plan_benefit_config_object CHECK (jsonb_typeof(configuration_json) = 'object')
);

-- ============================================================
-- 3. VERSIONED PRICING CONFIGURATION
-- ============================================================
