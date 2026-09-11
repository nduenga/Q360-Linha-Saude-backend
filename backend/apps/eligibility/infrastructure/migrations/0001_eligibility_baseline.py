"""Eligibility baseline schema (Q360-S3-03).

Ports Q360-MVP-ART-012 V014 verbatim via `RunSQL`. Depends on `product`
(product_version, plan), `client` (proposer, insured_member) and
`foundation` (tenant, rule_version) migrations for the FKs below.
"""
from django.db import migrations

V014_CREATE_ELIGIBILITY_EVALUATION = """
CREATE TABLE q360.eligibility_evaluation (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id         uuid REFERENCES q360.proposer(id),
    member_id           uuid REFERENCES q360.insured_member(id),
    product_version_id  uuid NOT NULL REFERENCES q360.product_version(id),
    plan_id             uuid NOT NULL REFERENCES q360.plan(id),
    rule_version_id     uuid REFERENCES q360.rule_version(id),
    decision            varchar(20) NOT NULL,
    input_snapshot_json jsonb NOT NULL,
    evidence_json       jsonb NOT NULL DEFAULT '[]'::jsonb,
    evaluated_at        timestamptz NOT NULL DEFAULT now(),
    correlation_id      varchar(100),
    CONSTRAINT ck_eligibility_decision CHECK (decision IN ('ELIGIBLE','WARNING','REFERRAL','HARD_STOP','CONFIG_ERROR')),
    CONSTRAINT ck_elig_input_object CHECK (jsonb_typeof(input_snapshot_json) = 'object'),
    CONSTRAINT ck_elig_evidence_array CHECK (jsonb_typeof(evidence_json) = 'array')
);
CREATE INDEX ix_eligibility_member ON q360.eligibility_evaluation(tenant_id, member_id, evaluated_at DESC);
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("foundation", "0002_rules_baseline"),
        ("product", "0001_product_baseline"),
        ("client", "0001_client_baseline"),
    ]
    operations = [
        migrations.RunSQL(sql=V014_CREATE_ELIGIBILITY_EVALUATION, reverse_sql=migrations.RunSQL.noop),
    ]
