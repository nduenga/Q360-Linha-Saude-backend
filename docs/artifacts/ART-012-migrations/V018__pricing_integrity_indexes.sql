-- Q360-MVP-ART-012 — Flyway Migration V018
-- File: V018__pricing_integrity_indexes.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE INDEX IF NOT EXISTS ix_pricing_trace_run ON q360.pricing_trace(tenant_id, pricing_run_id, sequence_no);
CREATE INDEX IF NOT EXISTS ix_pricing_scenario_created ON q360.pricing_scenario(tenant_id, created_at DESC);
DO $$ BEGIN IF to_regclass('q360.pricing_run') IS NULL OR to_regclass('q360.pricing_component') IS NULL OR to_regclass('q360.pricing_trace') IS NULL OR to_regclass('q360.pricing_scenario') IS NULL THEN RAISE EXCEPTION 'Q360 V018 prerequisite pricing tables are missing.'; END IF; END $$;
