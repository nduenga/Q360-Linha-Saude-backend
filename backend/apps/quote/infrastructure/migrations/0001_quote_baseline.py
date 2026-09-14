"""Quote baseline schema (Q360-S6-01..04).

Ports Q360-MVP-ART-012 V019, V020 and V021 verbatim via `RunSQL`, in order
— see apps/foundation's `0001_foundation_baseline.py` for the general
verbatim-migration policy.
"""
from django.db import migrations

V019_CREATE_QUOTE = """
CREATE TABLE q360.quote (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_number        varchar(100),
    proposer_id         uuid NOT NULL REFERENCES q360.proposer(id),
    product_version_id  uuid NOT NULL REFERENCES q360.product_version(id),
    plan_id             uuid NOT NULL REFERENCES q360.plan(id),
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    effective_date      date NOT NULL,
    valid_until         date,
    currency_code       char(3),
    latest_pricing_run_id uuid REFERENCES q360.pricing_run(id),
    submitted_by        varchar(200),
    submitted_at        timestamptz,
    approved_by         varchar(200),
    approved_at         timestamptz,
    rejected_by         varchar(200),
    rejected_at         timestamptz,
    cancellation_reason text,
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_quote_status CHECK (status IN ('DRAFT','READY','IN_REVIEW','APPROVED','REJECTED','EXPIRED','CANCELLED')),
    CONSTRAINT ck_quote_dates CHECK (valid_until IS NULL OR valid_until >= effective_date),
    CONSTRAINT ck_quote_currency CHECK (currency_code IS NULL OR currency_code ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_quote_four_eyes CHECK (approved_by IS NULL OR submitted_by IS NULL OR approved_by <> submitted_by),
    CONSTRAINT ck_quote_row_version CHECK (row_version >= 0)
);
CREATE UNIQUE INDEX uq_quote_number ON q360.quote(tenant_id, quote_number) WHERE quote_number IS NOT NULL;
CREATE INDEX ix_quote_proposer ON q360.quote(tenant_id, proposer_id, created_at DESC);
CREATE INDEX ix_quote_status ON q360.quote(tenant_id, status, updated_at DESC);
"""

V020_CREATE_QUOTE_MEMBERS_AND_SNAPSHOTS = """
CREATE TABLE q360.quote_member (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id            uuid NOT NULL REFERENCES q360.quote(id) ON DELETE CASCADE,
    member_id           uuid NOT NULL REFERENCES q360.insured_member(id),
    status              varchar(20) NOT NULL DEFAULT 'INCLUDED',
    eligibility_evaluation_id uuid REFERENCES q360.eligibility_evaluation(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_quote_member UNIQUE (tenant_id, quote_id, member_id),
    CONSTRAINT ck_quote_member_status CHECK (status IN ('INCLUDED','EXCLUDED','REFERRAL'))
);

CREATE TABLE q360.quote_snapshot (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id            uuid NOT NULL REFERENCES q360.quote(id),
    snapshot_no         integer NOT NULL,
    snapshot_type       varchar(30) NOT NULL,
    pricing_run_id      uuid REFERENCES q360.pricing_run(id),
    product_version_id  uuid NOT NULL REFERENCES q360.product_version(id),
    plan_id             uuid NOT NULL REFERENCES q360.plan(id),
    snapshot_json       jsonb NOT NULL,
    checksum            varchar(128) NOT NULL,
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_quote_snapshot_no UNIQUE (tenant_id, quote_id, snapshot_no),
    CONSTRAINT ck_quote_snapshot_no CHECK (snapshot_no > 0),
    CONSTRAINT ck_quote_snapshot_type CHECK (snapshot_type IN ('PRICING','SUBMISSION','APPROVAL','DOCUMENT')),
    CONSTRAINT ck_quote_snapshot_json CHECK (jsonb_typeof(snapshot_json) = 'object')
);
CREATE INDEX ix_quote_snapshot_quote ON q360.quote_snapshot(tenant_id, quote_id, snapshot_no DESC);
"""

V021_CREATE_QUOTE_STATE_HISTORY = """
CREATE TABLE q360.quote_state_history (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id            uuid NOT NULL REFERENCES q360.quote(id),
    from_status         varchar(20),
    to_status           varchar(20) NOT NULL,
    reason_code         varchar(100),
    reason_text         text,
    changed_by          varchar(200) NOT NULL,
    changed_at          timestamptz NOT NULL DEFAULT now(),
    correlation_id      varchar(100),
    CONSTRAINT ck_quote_history_to CHECK (to_status IN ('DRAFT','READY','IN_REVIEW','APPROVED','REJECTED','EXPIRED','CANCELLED')),
    CONSTRAINT ck_quote_history_from CHECK (from_status IS NULL OR from_status IN ('DRAFT','READY','IN_REVIEW','APPROVED','REJECTED','EXPIRED','CANCELLED'))
);
CREATE INDEX ix_quote_history ON q360.quote_state_history(tenant_id, quote_id, changed_at);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("client", "0001_client_baseline"),
        ("product", "0001_product_baseline"),
        ("pricing", "0002_pricing_engine"),
        ("eligibility", "0001_eligibility_baseline"),
    ]
    operations = [
        migrations.RunSQL(sql=V019_CREATE_QUOTE, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V020_CREATE_QUOTE_MEMBERS_AND_SNAPSHOTS, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V021_CREATE_QUOTE_STATE_HISTORY, reverse_sql=migrations.RunSQL.noop),
    ]
