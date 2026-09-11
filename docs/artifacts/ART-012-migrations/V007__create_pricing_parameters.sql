-- Q360-MVP-ART-012 — Flyway Migration V007
-- File: V007__create_pricing_parameters.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.pricing_parameter_set (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(80) NOT NULL,
    version_no          integer NOT NULL,
    effective_from      date NOT NULL,
    effective_to        date,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    checksum            varchar(128),
    published_at        timestamptz,
    published_by        varchar(200),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_pricing_parameter_set UNIQUE (tenant_id, code, version_no),
    CONSTRAINT ck_pps_version CHECK (version_no > 0),
    CONSTRAINT ck_pps_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_pps_status CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
    CONSTRAINT ck_pps_row_version CHECK (row_version >= 0)
);

CREATE TABLE q360.pricing_parameter (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    parameter_set_id    uuid NOT NULL REFERENCES q360.pricing_parameter_set(id),
    parameter_code      varchar(100) NOT NULL,
    value_type          varchar(20) NOT NULL,
    decimal_value       numeric(30,12),
    integer_value       bigint,
    boolean_value       boolean,
    text_value          text,
    json_value          jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_pricing_parameter UNIQUE (tenant_id, parameter_set_id, parameter_code),
    CONSTRAINT ck_pricing_parameter_type CHECK (value_type IN ('DECIMAL','INTEGER','BOOLEAN','TEXT','JSON')),
    CONSTRAINT ck_pricing_parameter_one_value CHECK (
        (value_type='DECIMAL' AND decimal_value IS NOT NULL AND integer_value IS NULL AND boolean_value IS NULL AND text_value IS NULL AND json_value IS NULL) OR
        (value_type='INTEGER' AND decimal_value IS NULL AND integer_value IS NOT NULL AND boolean_value IS NULL AND text_value IS NULL AND json_value IS NULL) OR
        (value_type='BOOLEAN' AND decimal_value IS NULL AND integer_value IS NULL AND boolean_value IS NOT NULL AND text_value IS NULL AND json_value IS NULL) OR
        (value_type='TEXT' AND decimal_value IS NULL AND integer_value IS NULL AND boolean_value IS NULL AND text_value IS NOT NULL AND json_value IS NULL) OR
        (value_type='JSON' AND decimal_value IS NULL AND integer_value IS NULL AND boolean_value IS NULL AND text_value IS NULL AND json_value IS NOT NULL)
    )
);
