"""Pricing engine schema (Q360-S4-02/S4-04/S5-02).

Ports Q360-MVP-ART-012 V015, V016, V017 and V018 verbatim via `RunSQL`, in
order — see `0001_pricing_baseline.py` for the general verbatim-migration
policy. `pricing_component` (V016) also creates `pricing_trace` in the
same file upstream (evidence + explainability share one migration file in
ART-012), kept together here too rather than split for cosmetic reasons.
"""
from django.db import migrations

V015_CREATE_PRICING_RUN = """
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
"""

V016_CREATE_PRICING_EVIDENCE = """
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
"""

V017_CREATE_PRICING_SCENARIO = """
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
"""

V018_PRICING_INTEGRITY_INDEXES = """
CREATE INDEX IF NOT EXISTS ix_pricing_trace_run ON q360.pricing_trace(tenant_id, pricing_run_id, sequence_no);
CREATE INDEX IF NOT EXISTS ix_pricing_scenario_created ON q360.pricing_scenario(tenant_id, created_at DESC);
DO $$ BEGIN IF to_regclass('q360.pricing_run') IS NULL OR to_regclass('q360.pricing_component') IS NULL OR to_regclass('q360.pricing_trace') IS NULL OR to_regclass('q360.pricing_scenario') IS NULL THEN RAISE EXCEPTION 'Q360 V018 prerequisite pricing tables are missing.'; END IF; END $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("pricing", "0001_pricing_baseline"),
        ("product", "0001_product_baseline"),
        ("client", "0001_client_baseline"),
        ("foundation", "0002_rules_baseline"),
    ]
    operations = [
        migrations.RunSQL(sql=V015_CREATE_PRICING_RUN, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V016_CREATE_PRICING_EVIDENCE, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V017_CREATE_PRICING_SCENARIO, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V018_PRICING_INTEGRITY_INDEXES, reverse_sql=migrations.RunSQL.noop),
    ]
