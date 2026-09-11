-- Q360-MVP-ART-012 — Flyway Migration V012
-- File: V012__create_rule_catalogue.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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
