"""Optional family households for corporate policyholders.

The previous population-group proposal was deliberately not exposed: a
company's population is represented by households (one holder plus zero or
more dependants), not organisational groups/subgroups.
"""
from django.db import migrations


SQL = """
CREATE TABLE q360.family_household (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id uuid NOT NULL REFERENCES q360.proposer(id),
    primary_member_id uuid NOT NULL UNIQUE REFERENCES q360.insured_member(id),
    status varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    row_version bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_family_household_status CHECK (status IN ('ACTIVE','INACTIVE'))
);
CREATE INDEX ix_family_household_proposer ON q360.family_household(tenant_id, proposer_id);
CREATE TABLE q360.family_household_member (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    household_id uuid NOT NULL REFERENCES q360.family_household(id),
    member_id uuid NOT NULL UNIQUE REFERENCES q360.insured_member(id),
    joined_at date NOT NULL,
    left_at date NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    row_version bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_family_household_member_dates CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE INDEX ix_family_household_member_active ON q360.family_household_member(tenant_id, household_id, left_at);
"""

REVERSE_SQL = """
DROP TABLE IF EXISTS q360.family_household_member;
DROP TABLE IF EXISTS q360.family_household;
"""


class Migration(migrations.Migration):
    dependencies = [("client", "0012_proposer_structured_location")]
    operations = [migrations.RunSQL(SQL, reverse_sql=REVERSE_SQL)]
