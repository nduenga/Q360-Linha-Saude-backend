-- Q360-MVP-ART-012 — Flyway Migration V023
-- File: V023__create_review_notes_and_decisions.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

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

-- ============================================================
-- 9. DOCUMENTS / NUMBERING
-- ============================================================
