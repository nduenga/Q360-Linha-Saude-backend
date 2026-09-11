-- Q360-MVP-ART-011 — Seed Data V1.0
-- PURPOSE: deterministic local/test bootstrap only.
-- IMPORTANT: This file intentionally contains NO tariff values, age thresholds,
-- authority limits, official currency, rounding policy, numbering convention,
-- real PII, clinical data, credentials or production secrets.
--
-- Deployment MUST set q360.environment. The DEV_TEST fixture section aborts
-- when the environment is production.

BEGIN;

-- ---------------------------------------------------------------------------
-- Stable IDs reserved for ART-011 local/test fixtures.
-- ---------------------------------------------------------------------------
-- Tenant:            00000000-0000-7000-8000-000000000001
-- Product:           00000000-0000-7000-8000-000000000101
-- Product Version:   00000000-0000-7000-8000-000000000102
-- Plan:              00000000-0000-7000-8000-000000000103
-- Benefit:           00000000-0000-7000-8000-000000000104
-- Parameter Set:     00000000-0000-7000-8000-000000000105
-- Rating Table:      00000000-0000-7000-8000-000000000106
-- Rule Sets:         ...201-204
-- Rule Versions:     ...211-214

DO $$
DECLARE
    env text := lower(coalesce(current_setting('q360.environment', true), ''));
BEGIN
    IF env NOT IN ('local','test') THEN
        RAISE EXCEPTION
          'Q360 ART-011 DEV_TEST seed refused: set q360.environment to local or test (current=%).',
          nullif(env,'');
    END IF;
END $$;

INSERT INTO q360.tenant (id, code, name, status)
VALUES ('00000000-0000-7000-8000-000000000001','Q360-DEMO','Q360 Demo Tenant','ACTIVE')
ON CONFLICT (code) DO NOTHING;

-- Technical rule-set identities. These rows contain no commercial values.
INSERT INTO q360.rule_set (id, tenant_id, code, name, rule_domain) VALUES
('00000000-0000-7000-8000-000000000201','00000000-0000-7000-8000-000000000001','ELIGIBILITY_V1','Q360 Eligibility V1','ELIGIBILITY'),
('00000000-0000-7000-8000-000000000202','00000000-0000-7000-8000-000000000001','PRICING_V1','Q360 Pricing V1','PRICING'),
('00000000-0000-7000-8000-000000000203','00000000-0000-7000-8000-000000000001','WORKFLOW_V1','Q360 Workflow V1','WORKFLOW'),
('00000000-0000-7000-8000-000000000204','00000000-0000-7000-8000-000000000001','VALIDATION_V1','Q360 Validation V1','VALIDATION')
ON CONFLICT (tenant_id, code) DO NOTHING;

-- Fictional DRAFT product shell.
INSERT INTO q360.product (id, tenant_id, code, name, description, status)
VALUES (
 '00000000-0000-7000-8000-000000000101',
 '00000000-0000-7000-8000-000000000001',
 'HEALTH-DEMO','Q360 Health Demo',
 'Synthetic local/test fixture. Not an approved commercial product.','DRAFT'
)
ON CONFLICT (tenant_id, code) DO NOTHING;

INSERT INTO q360.product_version
(id, tenant_id, product_id, version_no, effective_from, status)
VALUES (
 '00000000-0000-7000-8000-000000000102',
 '00000000-0000-7000-8000-000000000001',
 '00000000-0000-7000-8000-000000000101',
 1, DATE '2000-01-01', 'DRAFT'
)
ON CONFLICT (tenant_id, product_id, version_no) DO NOTHING;

INSERT INTO q360.plan
(id, tenant_id, product_version_id, code, name, description, status)
VALUES (
 '00000000-0000-7000-8000-000000000103',
 '00000000-0000-7000-8000-000000000001',
 '00000000-0000-7000-8000-000000000102',
 'DEMO-BASE','Demo Base Plan',
 'Synthetic shell; no benefit limits or tariff implied.','ACTIVE'
)
ON CONFLICT (tenant_id, product_version_id, code) DO NOTHING;

INSERT INTO q360.benefit
(id, tenant_id, code, name, benefit_type, description, status)
VALUES (
 '00000000-0000-7000-8000-000000000104',
 '00000000-0000-7000-8000-000000000001',
 'DEMO-BENEFIT','Demo Benefit Placeholder',NULL,
 'Synthetic placeholder with no coverage promise or limit.','ACTIVE'
)
ON CONFLICT (tenant_id, code) DO NOTHING;

-- Draft configuration shells. Deliberately no pricing_parameter or rating_factor rows.
INSERT INTO q360.pricing_parameter_set
(id, tenant_id, code, version_no, effective_from, status)
VALUES (
 '00000000-0000-7000-8000-000000000105',
 '00000000-0000-7000-8000-000000000001',
 'DEMO-PARAMS',1,DATE '2000-01-01','DRAFT'
)
ON CONFLICT (tenant_id, code, version_no) DO NOTHING;

INSERT INTO q360.rating_table
(id, tenant_id, code, name, version_no, effective_from, status, currency_code)
VALUES (
 '00000000-0000-7000-8000-000000000106',
 '00000000-0000-7000-8000-000000000001',
 'DEMO-RATING','Demo Rating Table',1,DATE '2000-01-01','DRAFT',NULL
)
ON CONFLICT (tenant_id, code, version_no) DO NOTHING;

-- Draft rule versions point to controlled artefacts; no rules are published by seed.
INSERT INTO q360.rule_version
(id, tenant_id, rule_set_id, version_no, effective_from, status, artifact_type, artifact_ref)
VALUES
('00000000-0000-7000-8000-000000000211','00000000-0000-7000-8000-000000000001','00000000-0000-7000-8000-000000000201',1,DATE '2000-01-01','DRAFT','DECISION_TABLE','Q360-MVP-ART-008#Eligibility'),
('00000000-0000-7000-8000-000000000212','00000000-0000-7000-8000-000000000001','00000000-0000-7000-8000-000000000202',1,DATE '2000-01-01','DRAFT','DECISION_TABLE','Q360-MVP-ART-008#Pricing'),
('00000000-0000-7000-8000-000000000213','00000000-0000-7000-8000-000000000001','00000000-0000-7000-8000-000000000203',1,DATE '2000-01-01','DRAFT','DECISION_TABLE','Q360-MVP-ART-008#Workflow;Q360-MVP-ART-009'),
('00000000-0000-7000-8000-000000000214','00000000-0000-7000-8000-000000000001','00000000-0000-7000-8000-000000000204',1,DATE '2000-01-01','DRAFT','DECISION_TABLE','Q360-MVP-ART-008#Validation')
ON CONFLICT (tenant_id, rule_set_id, version_no) DO NOTHING;

-- Guard assertions: ART-011 must not accidentally introduce commercial values.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM q360.rating_factor
        WHERE tenant_id='00000000-0000-7000-8000-000000000001'
          AND rating_table_id='00000000-0000-7000-8000-000000000106'
    ) THEN
        RAISE EXCEPTION 'ART-011 invariant violated: demo rating table contains rating factors.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM q360.pricing_parameter
        WHERE tenant_id='00000000-0000-7000-8000-000000000001'
          AND parameter_set_id='00000000-0000-7000-8000-000000000105'
    ) THEN
        RAISE EXCEPTION 'ART-011 invariant violated: demo parameter set contains commercial parameters.';
    END IF;
END $$;

COMMIT;
