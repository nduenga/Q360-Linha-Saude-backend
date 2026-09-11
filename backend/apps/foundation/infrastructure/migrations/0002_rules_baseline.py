"""Rules baseline schema (Q360-S3-03 dependency: `eligibility_evaluation`
has a hard FK to `rule_version`).

Ports Q360-MVP-ART-012 V012 and V013 verbatim via `RunSQL`, in order. See
`infrastructure/models.py` for why `RuleSet`/`RuleVersion` live in
`foundation` rather than a business module, and
`0001_foundation_baseline.py` for the general verbatim-migration policy.

V011 (`rating_table`/`rating_factor`) is deliberately NOT included here:
nothing built so far references it, so it is deferred to Sprint 4 when the
pricing module actually needs it — bringing it in now would be generating
schema ahead of an approved, consuming feature (DOC-000 s2 golden rule).
"""
from django.db import migrations

V012_CREATE_RULE_CATALOGUE = """
CREATE TABLE q360.rule_set (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(80) NOT NULL,
    name                varchar(200) NOT NULL,
    rule_domain         varchar(40) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_rule_set_code UNIQUE (tenant_id, code),
    CONSTRAINT ck_rule_domain CHECK (rule_domain IN ('ELIGIBILITY','PRICING','WORKFLOW','VALIDATION'))
);
"""

V013_CREATE_RULE_VERSIONS = """
CREATE TABLE q360.rule_version (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    rule_set_id         uuid NOT NULL REFERENCES q360.rule_set(id),
    version_no          integer NOT NULL,
    effective_from      date NOT NULL,
    effective_to        date,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    artifact_type       varchar(30) NOT NULL DEFAULT 'DECISION_TABLE',
    artifact_ref        text,
    artifact_checksum   varchar(128),
    published_at        timestamptz,
    published_by        varchar(200),
    approved_by         varchar(200),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_rule_version UNIQUE (tenant_id, rule_set_id, version_no),
    CONSTRAINT ck_rule_version_no CHECK (version_no > 0),
    CONSTRAINT ck_rule_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_rule_status CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
    CONSTRAINT ck_rule_artifact_type CHECK (artifact_type IN ('DRL','DECISION_TABLE','JSON','INTERNAL')),
    CONSTRAINT ck_rule_four_eyes CHECK (
        approved_by IS NULL OR published_by IS NULL OR approved_by <> published_by
    ),
    CONSTRAINT ck_rule_row_version CHECK (row_version >= 0)
);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0001_foundation_baseline")]
    operations = [
        migrations.RunSQL(sql=V012_CREATE_RULE_CATALOGUE, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V013_CREATE_RULE_VERSIONS, reverse_sql=migrations.RunSQL.noop),
    ]
