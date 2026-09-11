-- Q360-MVP-ART-012 — Flyway Migration V003
-- File: V003__create_audit_event.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.audit_event (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    actor_id            varchar(200),
    actor_type          varchar(30) NOT NULL DEFAULT 'USER',
    action              varchar(120) NOT NULL,
    entity_type         varchar(120) NOT NULL,
    entity_id           varchar(200),
    occurred_at         timestamptz NOT NULL DEFAULT now(),
    correlation_id      varchar(100),
    trace_id            varchar(100),
    source              varchar(100),
    metadata_json       jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_audit_actor_type CHECK (actor_type IN ('USER','SYSTEM','SERVICE')),
    CONSTRAINT ck_audit_metadata_object CHECK (jsonb_typeof(metadata_json) = 'object')
);
CREATE INDEX ix_audit_tenant_occurred ON q360.audit_event(tenant_id, occurred_at DESC);
CREATE INDEX ix_audit_entity ON q360.audit_event(tenant_id, entity_type, entity_id);
CREATE INDEX ix_audit_correlation ON q360.audit_event(correlation_id) WHERE correlation_id IS NOT NULL;

-- ============================================================
-- 2. PRODUCT / PLAN / BENEFIT
-- ============================================================
