"""Review workflow schema (Q360-S7-01..03).

Ports Q360-MVP-ART-012 V022 and V023 verbatim via `RunSQL`, in order.
"""
from django.db import migrations

V022_CREATE_AUTHORITY_AND_REVIEW = """
CREATE TABLE q360.authority_policy (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(80) NOT NULL,
    version_no          integer NOT NULL,
    effective_from      date NOT NULL,
    effective_to        date,
    status              varchar(20) NOT NULL DEFAULT 'DRAFT',
    policy_json         jsonb NOT NULL,
    checksum            varchar(128),
    published_at        timestamptz,
    published_by        varchar(200),
    approved_by         varchar(200),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_authority_policy UNIQUE (tenant_id, code, version_no),
    CONSTRAINT ck_authority_version CHECK (version_no > 0),
    CONSTRAINT ck_authority_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_authority_status CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
    CONSTRAINT ck_authority_policy_json CHECK (jsonb_typeof(policy_json) = 'object'),
    CONSTRAINT ck_authority_four_eyes CHECK (approved_by IS NULL OR published_by IS NULL OR approved_by <> published_by)
);

CREATE TABLE q360.review_task (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id            uuid NOT NULL REFERENCES q360.quote(id),
    status              varchar(20) NOT NULL DEFAULT 'OPEN',
    assigned_to         varchar(200),
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    started_at          timestamptz,
    decided_at          timestamptz,
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT ck_review_status CHECK (status IN ('OPEN','IN_PROGRESS','DECIDED','RETURNED')),
    CONSTRAINT ck_review_row_version CHECK (row_version >= 0)
);
CREATE INDEX ix_review_queue ON q360.review_task(tenant_id, status, created_at);
"""

V023_CREATE_REVIEW_NOTES_AND_DECISIONS = """
CREATE TABLE q360.review_note (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    review_task_id      uuid NOT NULL REFERENCES q360.review_task(id) ON DELETE CASCADE,
    note_text           text NOT NULL,
    created_by          varchar(200) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE q360.quote_decision (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id            uuid NOT NULL REFERENCES q360.quote(id),
    review_task_id      uuid REFERENCES q360.review_task(id),
    authority_policy_id uuid REFERENCES q360.authority_policy(id),
    decision            varchar(20) NOT NULL,
    reason_code         varchar(100) NOT NULL,
    reason_text         text,
    decided_by          varchar(200) NOT NULL,
    submitted_by        varchar(200),
    decided_at          timestamptz NOT NULL DEFAULT now(),
    snapshot_id         uuid REFERENCES q360.quote_snapshot(id),
    CONSTRAINT ck_quote_decision CHECK (decision IN ('APPROVE','REJECT','RETURN')),
    CONSTRAINT ck_decision_four_eyes CHECK (submitted_by IS NULL OR decided_by <> submitted_by)
);
CREATE INDEX ix_quote_decision_quote ON q360.quote_decision(tenant_id, quote_id, decided_at DESC);
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0001_quote_baseline")]
    operations = [
        migrations.RunSQL(sql=V022_CREATE_AUTHORITY_AND_REVIEW, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=V023_CREATE_REVIEW_NOTES_AND_DECISIONS, reverse_sql=migrations.RunSQL.noop),
    ]
