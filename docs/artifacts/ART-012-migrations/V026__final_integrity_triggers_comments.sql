-- Q360-MVP-ART-012 — Flyway Migration V026
-- File: V026__final_integrity_triggers_comments.sql
-- PostgreSQL 15+ | Status: REVIEW | Forward-only
-- No unresolved commercial values are introduced.

CREATE OR REPLACE FUNCTION q360.assert_same_tenant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_tenant uuid;
    parent_table text := TG_ARGV[0];
    parent_column text := TG_ARGV[1];
    fk_column text := TG_ARGV[2];
    fk_value uuid;
BEGIN
    fk_value := NULLIF(to_jsonb(NEW) ->> fk_column, '')::uuid;
    IF fk_value IS NULL THEN
        RETURN NEW;
    END IF;

    EXECUTE format('SELECT tenant_id FROM q360.%I WHERE %I = $1', parent_table, parent_column)
       INTO parent_tenant USING fk_value;

    IF parent_tenant IS NULL THEN
        RAISE EXCEPTION 'Referenced parent not found for %.%', parent_table, fk_value
            USING ERRCODE = '23503';
    END IF;

    IF parent_tenant <> NEW.tenant_id THEN
        RAISE EXCEPTION 'Cross-tenant reference prohibited: table %, parent %', TG_TABLE_NAME, parent_table
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

-- High-risk aggregate references. Additional triggers may be added by ART-012.
CREATE TRIGGER trg_product_version_tenant
BEFORE INSERT OR UPDATE ON q360.product_version
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('product','id','product_id');

CREATE TRIGGER trg_plan_tenant
BEFORE INSERT OR UPDATE ON q360.plan
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('product_version','id','product_version_id');

CREATE TRIGGER trg_member_proposer_tenant
BEFORE INSERT OR UPDATE ON q360.insured_member
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('proposer','id','proposer_id');

CREATE TRIGGER trg_quote_proposer_tenant
BEFORE INSERT OR UPDATE ON q360.quote
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('proposer','id','proposer_id');

CREATE TRIGGER trg_quote_product_version_tenant
BEFORE INSERT OR UPDATE ON q360.quote
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('product_version','id','product_version_id');

CREATE TRIGGER trg_quote_plan_tenant
BEFORE INSERT OR UPDATE ON q360.quote
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('plan','id','plan_id');

CREATE TRIGGER trg_quote_member_quote_tenant
BEFORE INSERT OR UPDATE ON q360.quote_member
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('quote','id','quote_id');

CREATE TRIGGER trg_quote_member_member_tenant
BEFORE INSERT OR UPDATE ON q360.quote_member
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('insured_member','id','member_id');

CREATE TRIGGER trg_pricing_component_run_tenant
BEFORE INSERT OR UPDATE ON q360.pricing_component
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('pricing_run','id','pricing_run_id');

CREATE TRIGGER trg_quote_snapshot_quote_tenant
BEFORE INSERT OR UPDATE ON q360.quote_snapshot
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('quote','id','quote_id');

CREATE TRIGGER trg_review_task_quote_tenant
BEFORE INSERT OR UPDATE ON q360.review_task
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('quote','id','quote_id');

CREATE TRIGGER trg_document_quote_tenant
BEFORE INSERT OR UPDATE ON q360.document
FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('quote','id','quote_id');

-- ============================================================
-- 12. IMMUTABILITY GUARDS FOR CONTROLLED SNAPSHOTS / RESULTS
-- ============================================================

CREATE OR REPLACE FUNCTION q360.reject_update_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Immutable Q360 record cannot be updated or deleted: %.%', TG_TABLE_SCHEMA, TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER trg_quote_snapshot_immutable
BEFORE UPDATE OR DELETE ON q360.quote_snapshot
FOR EACH ROW EXECUTE FUNCTION q360.reject_update_delete();

CREATE TRIGGER trg_pricing_component_immutable
BEFORE UPDATE OR DELETE ON q360.pricing_component
FOR EACH ROW EXECUTE FUNCTION q360.reject_update_delete();

CREATE TRIGGER trg_pricing_trace_immutable
BEFORE UPDATE OR DELETE ON q360.pricing_trace
FOR EACH ROW EXECUTE FUNCTION q360.reject_update_delete();

CREATE TRIGGER trg_quote_decision_immutable
BEFORE UPDATE OR DELETE ON q360.quote_decision
FOR EACH ROW EXECUTE FUNCTION q360.reject_update_delete();

CREATE TRIGGER trg_audit_event_immutable
BEFORE UPDATE OR DELETE ON q360.audit_event
FOR EACH ROW EXECUTE FUNCTION q360.reject_update_delete();

-- ============================================================
-- 13. COMMENTS / GOVERNANCE NOTES
-- ============================================================

COMMENT ON SCHEMA q360 IS 'Q360 Health Underwriting & Pricing Core V1 application schema';
COMMENT ON TABLE q360.quote_snapshot IS 'Immutable reproducibility snapshot. Never mutate historical snapshots.';
COMMENT ON TABLE q360.pricing_run IS 'Deterministic pricing execution with exact version references.';
COMMENT ON TABLE q360.pricing_component IS 'Immutable component-level pricing breakdown used for explainability and Golden Tests.';
COMMENT ON TABLE q360.outbox_event IS 'Transactional outbox. Written in same DB transaction as business state.';
COMMENT ON TABLE q360.idempotency_record IS 'HTTP/command idempotency record. Retention policy is operationally configurable.';
COMMENT ON COLUMN q360.proposer.attributes_json IS 'Temporary extensibility for OD-003; governed, not a replacement for approved structured fields.';
COMMENT ON COLUMN q360.insured_member.attributes_json IS 'Temporary extensibility for OD-003; sensitive/clinical data must not be stored here without explicit design approval.';

CREATE TRIGGER trg_pricing_run_product_version_tenant BEFORE INSERT OR UPDATE ON q360.pricing_run FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('product_version','id','product_version_id');
CREATE TRIGGER trg_pricing_run_plan_tenant BEFORE INSERT OR UPDATE ON q360.pricing_run FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('plan','id','plan_id');
CREATE TRIGGER trg_review_note_task_tenant BEFORE INSERT OR UPDATE ON q360.review_note FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('review_task','id','review_task_id');
CREATE TRIGGER trg_quote_decision_quote_tenant BEFORE INSERT OR UPDATE ON q360.quote_decision FOR EACH ROW EXECUTE FUNCTION q360.assert_same_tenant('quote','id','quote_id');
DO $$ DECLARE actual_tables integer; BEGIN SELECT count(*) INTO actual_tables FROM information_schema.tables WHERE table_schema='q360' AND table_type='BASE TABLE'; IF actual_tables < 36 THEN RAISE EXCEPTION 'Q360 schema incomplete: expected at least 36 tables, found %.', actual_tables; END IF; END $$;
