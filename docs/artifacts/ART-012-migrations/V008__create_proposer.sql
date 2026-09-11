-- Q360-MVP-ART-012 — Flyway Migration V008
-- File: V008__create_proposer.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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
