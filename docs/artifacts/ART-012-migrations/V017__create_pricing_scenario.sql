-- Q360-MVP-ART-012 — Flyway Migration V017
-- File: V017__create_pricing_scenario.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.pricing_scenario (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    base_pricing_run_id uuid REFERENCES q360.pricing_run(id),
    name                varchar(200) NOT NULL,
    input_override_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_pricing_run_id uuid REFERENCES q360.pricing_run(id),
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_pricing_scenario_override CHECK (jsonb_typeof(input_override_json) = 'object')
);

-- ============================================================
-- 7. QUOTATION
-- ============================================================
