-- Q360-MVP-ART-012 — Flyway Migration V020
-- File: V020__create_quote_members_and_snapshots.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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
