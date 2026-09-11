"""Client baseline schema (Q360-S3-01, S3-02, S3-04).

Ports Q360-MVP-ART-012 V008, V009 and V010 verbatim via `RunSQL`, in order.
Do not edit without first updating the ART-012 source of truth and
recording a Change Request (DOC-000 s12). See
apps/foundation/infrastructure/migrations/0001_foundation_baseline.py for
the general verbatim-migration and forward-only-rollback policy.
"""
from django.db import migrations

V008_CREATE_PROPOSER = """
CREATE TABLE q360.proposer (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_type       varchar(20) NOT NULL,
    external_reference  varchar(100),
    display_name        varchar(250) NOT NULL,
    registration_number varchar(100),
    attributes_json     jsonb NOT NULL DEFAULT '{}'::jsonb,
    status              varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_proposer_type CHECK (proposer_type IN ('INDIVIDUAL','ORGANISATION')),
    CONSTRAINT ck_proposer_status CHECK (status IN ('ACTIVE','INACTIVE')),
    CONSTRAINT ck_proposer_attributes CHECK (jsonb_typeof(attributes_json) = 'object'),
    CONSTRAINT ck_proposer_row_version CHECK (row_version >= 0)
);
CREATE UNIQUE INDEX uq_proposer_external_ref ON q360.proposer(tenant_id, external_reference)
WHERE external_reference IS NOT NULL;
"""

V009_CREATE_INSURED_MEMBER = """
CREATE TABLE q360.insured_member (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id         uuid NOT NULL REFERENCES q360.proposer(id),
    external_reference  varchar(100),
    relationship_code   varchar(40) NOT NULL,
    first_name          varchar(120),
    last_name           varchar(120),
    date_of_birth       date,
    sex_code            varchar(20),
    attributes_json     jsonb NOT NULL DEFAULT '{}'::jsonb,
    status              varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_member_status CHECK (status IN ('ACTIVE','INACTIVE')),
    CONSTRAINT ck_member_attributes CHECK (jsonb_typeof(attributes_json) = 'object'),
    CONSTRAINT ck_member_row_version CHECK (row_version >= 0)
);
CREATE UNIQUE INDEX uq_member_external_ref ON q360.insured_member(tenant_id, proposer_id, external_reference)
WHERE external_reference IS NOT NULL;
CREATE INDEX ix_member_proposer ON q360.insured_member(tenant_id, proposer_id);
"""

V010_CREATE_IMPORT_JOB = """
CREATE TABLE q360.import_job (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id         uuid REFERENCES q360.proposer(id),
    import_type         varchar(30) NOT NULL,
    original_filename   varchar(255),
    file_checksum       varchar(128),
    status              varchar(20) NOT NULL DEFAULT 'UPLOADED',
    total_rows          integer NOT NULL DEFAULT 0,
    valid_rows          integer NOT NULL DEFAULT 0,
    invalid_rows        integer NOT NULL DEFAULT 0,
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    CONSTRAINT ck_import_type CHECK (import_type IN ('MEMBER_POPULATION')),
    CONSTRAINT ck_import_status CHECK (status IN ('UPLOADED','VALIDATING','VALIDATED','COMMITTING','COMPLETED','FAILED')),
    CONSTRAINT ck_import_counts CHECK (total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0)
);

CREATE TABLE q360.import_row_error (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    import_job_id       uuid NOT NULL REFERENCES q360.import_job(id) ON DELETE CASCADE,
    row_number          integer NOT NULL,
    field_name          varchar(120),
    error_code          varchar(80) NOT NULL,
    error_message       text NOT NULL,
    raw_value_masked    text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_import_row_number CHECK (row_number > 0)
);
CREATE INDEX ix_import_error_job ON q360.import_row_error(tenant_id, import_job_id, row_number);
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = [("foundation", "0001_foundation_baseline")]
    operations = [
        migrations.RunSQL(sql=V008_CREATE_PROPOSER, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V009_CREATE_INSURED_MEMBER, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V010_CREATE_IMPORT_JOB, reverse_sql=migrations.RunSQL.noop),
    ]
