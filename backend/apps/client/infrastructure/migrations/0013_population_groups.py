"""Groups, subgroups and membership categories for corporate populations."""
from django.db import migrations


SQL = """
CREATE TABLE q360.population_group (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id uuid NOT NULL REFERENCES q360.proposer(id),
    parent_group_id uuid NULL REFERENCES q360.population_group(id),
    code varchar(60) NOT NULL,
    name varchar(200) NOT NULL,
    category_code varchar(60) NULL,
    eligibility_rules_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    row_version bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_population_group_code UNIQUE (tenant_id, proposer_id, code),
    CONSTRAINT ck_population_group_status CHECK (status IN ('ACTIVE','INACTIVE'))
);
CREATE INDEX ix_population_group_proposer ON q360.population_group(tenant_id, proposer_id, parent_group_id);
CREATE TABLE q360.population_group_member (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    group_id uuid NOT NULL REFERENCES q360.population_group(id),
    member_id uuid NOT NULL REFERENCES q360.insured_member(id),
    category_code varchar(60) NULL,
    joined_at date NOT NULL,
    left_at date NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    row_version bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_population_group_member UNIQUE (group_id, member_id),
    CONSTRAINT ck_population_group_member_dates CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE INDEX ix_population_group_member_active ON q360.population_group_member(tenant_id, group_id, left_at);
"""

REVERSE_SQL = """
DROP TABLE IF EXISTS q360.population_group_member;
DROP TABLE IF EXISTS q360.population_group;
"""


class Migration(migrations.Migration):
    dependencies = [("client", "0012_proposer_structured_location")]
    operations = [migrations.RunSQL(SQL, reverse_sql=REVERSE_SQL)]
