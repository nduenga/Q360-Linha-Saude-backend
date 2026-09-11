-- Q360-MVP-ART-012 — Flyway Migration V016
-- File: V016__create_pricing_evidence.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.pricing_component (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    pricing_run_id      uuid NOT NULL REFERENCES q360.pricing_run(id) ON DELETE CASCADE,
    member_id           uuid REFERENCES q360.insured_member(id),
    component_order     integer NOT NULL,
    component_code      varchar(100) NOT NULL,
    component_type      varchar(30) NOT NULL,
    base_amount         numeric(30,8),
    factor_value        numeric(30,12),
    adjustment_amount   numeric(30,8),
    result_amount       numeric(30,8) NOT NULL,
    source_code         varchar(120),
    source_version      varchar(80),
    metadata_json       jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_pricing_component_order UNIQUE (tenant_id, pricing_run_id, component_order),
    CONSTRAINT ck_pricing_component_order CHECK (component_order >= 0),
    CONSTRAINT ck_pricing_component_type CHECK (component_type IN ('BASE','FACTOR','ADJUSTMENT','FEE','TAX','TOTAL','OTHER')),
    CONSTRAINT ck_pricing_component_metadata CHECK (jsonb_typeof(metadata_json) = 'object')
);
CREATE INDEX ix_pricing_component_run ON q360.pricing_component(tenant_id, pricing_run_id);

CREATE TABLE q360.pricing_trace (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    pricing_run_id      uuid NOT NULL REFERENCES q360.pricing_run(id) ON DELETE CASCADE,
    sequence_no         integer NOT NULL,
    step_code           varchar(100) NOT NULL,
    rule_code           varchar(120),
    input_json          jsonb,
    output_json         jsonb,
    message             text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_pricing_trace_sequence UNIQUE (tenant_id, pricing_run_id, sequence_no),
    CONSTRAINT ck_pricing_trace_sequence CHECK (sequence_no >= 0)
);
