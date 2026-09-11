-- Q360-MVP-ART-012 — Flyway Migration V015
-- File: V015__create_pricing_run.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.pricing_run (
    id                      uuid PRIMARY KEY,
    tenant_id               uuid NOT NULL REFERENCES q360.tenant(id),
    product_version_id      uuid NOT NULL REFERENCES q360.product_version(id),
    plan_id                 uuid NOT NULL REFERENCES q360.plan(id),
    rating_table_id         uuid NOT NULL REFERENCES q360.rating_table(id),
    parameter_set_id        uuid NOT NULL REFERENCES q360.pricing_parameter_set(id),
    rule_version_id         uuid REFERENCES q360.rule_version(id),
    status                  varchar(20) NOT NULL DEFAULT 'REQUESTED',
    effective_date          date NOT NULL,
    currency_code           char(3) NOT NULL,
    rounding_policy_code    varchar(80) NOT NULL,
    rounding_policy_version integer NOT NULL,
    input_snapshot_json     jsonb NOT NULL,
    total_amount            numeric(30,8),
    started_at              timestamptz,
    completed_at            timestamptz,
    failure_code            varchar(100),
    failure_message_safe    text,
    correlation_id          varchar(100),
    created_at              timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_pricing_status CHECK (status IN ('REQUESTED','CALCULATING','CALCULATED','FAILED')),
    CONSTRAINT ck_pricing_currency CHECK (currency_code ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_rounding_version CHECK (rounding_policy_version > 0),
    CONSTRAINT ck_pricing_input_object CHECK (jsonb_typeof(input_snapshot_json) = 'object'),
    CONSTRAINT ck_pricing_result_consistency CHECK (
        (status='CALCULATED' AND total_amount IS NOT NULL AND completed_at IS NOT NULL)
        OR status <> 'CALCULATED'
    ),
    CONSTRAINT ck_pricing_failure_consistency CHECK (
        (status='FAILED' AND failure_code IS NOT NULL)
        OR status <> 'FAILED'
    )
);
CREATE INDEX ix_pricing_run_tenant_created ON q360.pricing_run(tenant_id, created_at DESC);
CREATE INDEX ix_pricing_run_versions ON q360.pricing_run(tenant_id, product_version_id, rating_table_id, parameter_set_id);
