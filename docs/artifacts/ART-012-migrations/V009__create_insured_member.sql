-- Q360-MVP-ART-012 — Flyway Migration V009
-- File: V009__create_insured_member.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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
