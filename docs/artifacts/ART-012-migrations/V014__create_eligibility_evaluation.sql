-- Q360-MVP-ART-012 — Flyway Migration V014
-- File: V014__create_eligibility_evaluation.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE TABLE q360.eligibility_evaluation (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id         uuid REFERENCES q360.proposer(id),
    member_id           uuid REFERENCES q360.insured_member(id),
    product_version_id  uuid NOT NULL REFERENCES q360.product_version(id),
    plan_id             uuid NOT NULL REFERENCES q360.plan(id),
    rule_version_id     uuid REFERENCES q360.rule_version(id),
    decision            varchar(20) NOT NULL,
    input_snapshot_json jsonb NOT NULL,
    evidence_json       jsonb NOT NULL DEFAULT '[]'::jsonb,
    evaluated_at        timestamptz NOT NULL DEFAULT now(),
    correlation_id      varchar(100),
    CONSTRAINT ck_eligibility_decision CHECK (decision IN ('ELIGIBLE','WARNING','REFERRAL','HARD_STOP','CONFIG_ERROR')),
    CONSTRAINT ck_elig_input_object CHECK (jsonb_typeof(input_snapshot_json) = 'object'),
    CONSTRAINT ck_elig_evidence_array CHECK (jsonb_typeof(evidence_json) = 'array')
);
CREATE INDEX ix_eligibility_member ON q360.eligibility_evaluation(tenant_id, member_id, evaluated_at DESC);

-- ============================================================
-- 6. PRICING EXECUTION / EXPLAINABILITY
-- ============================================================
