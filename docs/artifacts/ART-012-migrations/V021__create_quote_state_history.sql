-- Q360-MVP-ART-012 — Flyway Migration V021
-- File: V021__create_quote_state_history.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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

-- ============================================================
-- 8. UNDERWRITING / AUTHORITY
-- ============================================================
