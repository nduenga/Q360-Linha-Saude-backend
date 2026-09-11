-- Q360-MVP-ART-012 — Flyway Migration V013
-- File: V013__create_rule_versions.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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

-- ============================================================
-- 4. CLIENT / POPULATION
-- Exact business identity fields remain subject to OD-003.
-- Extensible attributes are isolated in attributes_json and must not
-- become an excuse to bypass later schema governance.
-- ============================================================
