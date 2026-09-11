"""Product baseline schema (Q360-S2-01, S2-02, S2-03).

Ports Q360-MVP-ART-012 V004, V005, V006 and V007 verbatim via `RunSQL`, in
order. Do not edit the SQL below without first updating the ART-012 source
of truth (docs/artifacts/ART-012-migrations/) and recording a Change
Request (DOC-000 s12). See infrastructure/models.py for why the matching
Django models are declared `managed = False`.

`reverse_sql` is a deliberate no-op — see the foundation module's baseline
migration for the forward-only rollback policy this follows.
"""
from django.db import migrations

V004_CREATE_PRODUCT = """
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
"""

V005_CREATE_PRODUCT_VERSION = """
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
"""

V006_CREATE_PLAN_AND_BENEFIT = """
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
"""

V007_CREATE_PRICING_PARAMETERS = """
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
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = [("foundation", "0001_foundation_baseline")]
    operations = [
        migrations.RunSQL(sql=V004_CREATE_PRODUCT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V005_CREATE_PRODUCT_VERSION, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V006_CREATE_PLAN_AND_BENEFIT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V007_CREATE_PRICING_PARAMETERS, reverse_sql=migrations.RunSQL.noop),
    ]
