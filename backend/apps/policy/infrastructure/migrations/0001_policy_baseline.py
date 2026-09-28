"""Policy baseline schema (ROADMAP_APOLICES.md Fase 2).

Not a port of an ART-012 artifact (this module postdates ART-005/ART-012)
— `DECISIONS_TAKEN.md#S09-POLICY-001` + `ROADMAP_APOLICES.md` are this
schema's own source of truth, same as every other RunSQL migration in
this project is `managed = False` and forward-only (see apps.foundation's
`0001_foundation_baseline.py` for the general policy this follows).

Deliberately NOT included yet (dangling-FK avoidance — added in the
migration that introduces their referenced table):
  - `policy.intermediary_id` / `policy_commission` (Fase 5: no
    `intermediary` table exists yet).
"""
from django.db import migrations

V001_CREATE_POLICY = """
CREATE TABLE q360.policy (
    id                          uuid PRIMARY KEY,
    tenant_id                   uuid NOT NULL REFERENCES q360.tenant(id),
    policy_number                varchar(100),
    source_quote_id             uuid NOT NULL REFERENCES q360.quote(id),
    contracted_terms_snapshot_id uuid NOT NULL REFERENCES q360.quote_snapshot(id),
    proposer_id                  uuid NOT NULL REFERENCES q360.proposer(id),
    plan_id                      uuid NOT NULL REFERENCES q360.plan(id),
    policy_type                  varchar(20) NOT NULL,
    term_months                  integer NOT NULL,
    start_date                   date,
    end_date                     date,
    status                       varchar(30) NOT NULL DEFAULT 'PENDING_FIRST_PREMIUM',
    payment_frequency            varchar(20) NOT NULL,
    currency_code                char(3),
    cancellation_reason_code     varchar(100),
    cancellation_effective_date  date,
    cancelled_by                 varchar(200),
    cancelled_at                 timestamptz,
    termination_reason_code      varchar(100),
    terminated_at                timestamptz,
    issued_by                    varchar(200) NOT NULL,
    issued_at                    timestamptz NOT NULL DEFAULT now(),
    created_at                   timestamptz NOT NULL DEFAULT now(),
    updated_at                   timestamptz NOT NULL DEFAULT now(),
    row_version                  bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_policy_source_quote UNIQUE (source_quote_id),
    CONSTRAINT uq_policy_number UNIQUE (tenant_id, policy_number),
    CONSTRAINT ck_policy_type CHECK (policy_type IN ('INDIVIDUAL','GROUP')),
    CONSTRAINT ck_policy_status CHECK (status IN
        ('PENDING_FIRST_PREMIUM','ACTIVE','SUSPENDED','TERMINATED','CANCELLED','EXPIRED','RENEWED')),
    CONSTRAINT ck_policy_payment_frequency CHECK (payment_frequency IN
        ('ANUAL','SEMESTRAL','TRIMESTRAL','MENSAL')),
    CONSTRAINT ck_policy_term_months CHECK (term_months > 0),
    CONSTRAINT ck_policy_dates CHECK (
        (start_date IS NULL AND end_date IS NULL) OR
        (start_date IS NOT NULL AND end_date IS NOT NULL AND end_date >= start_date)
    ),
    CONSTRAINT ck_policy_currency CHECK (currency_code IS NULL OR currency_code ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_policy_row_version CHECK (row_version >= 0)
);
CREATE UNIQUE INDEX uq_policy_number_notnull ON q360.policy(tenant_id, policy_number) WHERE policy_number IS NOT NULL;
CREATE INDEX ix_policy_proposer ON q360.policy(tenant_id, proposer_id, created_at DESC);
CREATE INDEX ix_policy_status ON q360.policy(tenant_id, status, updated_at DESC);
"""

V002_CREATE_POLICY_SIGNATURE = """
CREATE TABLE q360.policy_signature (
    id                          uuid PRIMARY KEY,
    tenant_id                   uuid NOT NULL REFERENCES q360.tenant(id),
    policy_id                   uuid NOT NULL REFERENCES q360.policy(id),
    signatory_name               varchar(250) NOT NULL,
    signatory_document_type      varchar(30) NOT NULL,
    signatory_document_number    varchar(100) NOT NULL,
    signatory_capacity           varchar(30) NOT NULL,
    signature_method             varchar(20) NOT NULL DEFAULT 'PRESENCIAL',
    signed_at                    timestamptz NOT NULL,
    signed_document_ref          text,
    signed_document_checksum     varchar(128),
    registered_by                varchar(200) NOT NULL,
    registered_at                timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_policy_signature UNIQUE (policy_id),
    CONSTRAINT ck_policy_signature_doc_type CHECK (signatory_document_type IN
        ('BI','CARTAO_RESIDENTE','PASSAPORTE_VISTO_TRABALHO')),
    CONSTRAINT ck_policy_signature_capacity CHECK (signatory_capacity IN
        ('TOMADOR','REPRESENTANTE_LEGAL','PROCURADOR')),
    CONSTRAINT ck_policy_signature_method CHECK (signature_method IN ('PRESENCIAL','DIGITAL'))
);
"""

V003_CREATE_POLICY_MEMBER = """
CREATE TABLE q360.policy_member (
    id                          uuid PRIMARY KEY,
    tenant_id                   uuid NOT NULL REFERENCES q360.tenant(id),
    policy_id                   uuid NOT NULL REFERENCES q360.policy(id),
    member_id                   uuid NOT NULL REFERENCES q360.insured_member(id),
    status                      varchar(20) NOT NULL DEFAULT 'PENDING',
    pending_reason_code         varchar(100),
    inclusion_date               date,
    exclusion_date               date,
    eligibility_evaluation_id    uuid REFERENCES q360.eligibility_evaluation(id),
    rule_version_id               uuid REFERENCES q360.rule_version(id),
    waiting_period_ends_json      jsonb NOT NULL DEFAULT '{}',
    loading_percentage            numeric(6,2),
    row_version                  bigint NOT NULL DEFAULT 0,
    created_at                   timestamptz NOT NULL DEFAULT now(),
    updated_at                   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_policy_member UNIQUE (tenant_id, policy_id, member_id),
    CONSTRAINT ck_policy_member_status CHECK (status IN ('PENDING','ACTIVE','EXCLUDED','REJECTED')),
    CONSTRAINT ck_policy_member_dates CHECK (exclusion_date IS NULL OR inclusion_date IS NULL OR exclusion_date >= inclusion_date),
    CONSTRAINT ck_policy_member_waiting_period_json CHECK (jsonb_typeof(waiting_period_ends_json) = 'object'),
    CONSTRAINT ck_policy_member_row_version CHECK (row_version >= 0)
);
CREATE INDEX ix_policy_member_policy ON q360.policy_member(tenant_id, policy_id);
"""

V004_CREATE_PREMIUM_INSTALLMENT = """
CREATE TABLE q360.premium_installment (
    id                          uuid PRIMARY KEY,
    tenant_id                   uuid NOT NULL REFERENCES q360.tenant(id),
    policy_id                   uuid NOT NULL REFERENCES q360.policy(id),
    installment_no               integer NOT NULL,
    period_from                  date NOT NULL,
    period_to                    date NOT NULL,
    due_date                     date NOT NULL,
    amount                       numeric(30,8) NOT NULL,
    currency_code                char(3) NOT NULL,
    status                       varchar(20) NOT NULL DEFAULT 'DUE',
    paid_at                      timestamptz,
    payment_reference             varchar(200),
    payment_method                varchar(50),
    registered_by                 varchar(200),
    created_at                   timestamptz NOT NULL DEFAULT now(),
    updated_at                   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_premium_installment UNIQUE (tenant_id, policy_id, installment_no),
    CONSTRAINT ck_premium_installment_status CHECK (status IN ('DUE','PAID','OVERDUE','VOID')),
    CONSTRAINT ck_premium_installment_period CHECK (period_to >= period_from),
    CONSTRAINT ck_premium_installment_amount CHECK (amount >= 0),
    CONSTRAINT ck_premium_installment_currency CHECK (currency_code ~ '^[A-Z]{3}$')
);
CREATE INDEX ix_premium_installment_policy ON q360.premium_installment(tenant_id, policy_id, installment_no);
CREATE INDEX ix_premium_installment_due ON q360.premium_installment(tenant_id, status, due_date);
"""

V005_CREATE_PREMIUM_DEFAULT_NOTICE = """
CREATE TABLE q360.premium_default_notice (
    id                          uuid PRIMARY KEY,
    tenant_id                   uuid NOT NULL REFERENCES q360.tenant(id),
    installment_id               uuid NOT NULL REFERENCES q360.premium_installment(id),
    sent_at                      timestamptz NOT NULL,
    registered_mail_reference     varchar(200) NOT NULL,
    new_deadline                  date NOT NULL,
    suspension_effective_at       timestamptz,
    outcome                       varchar(20),
    registered_by                 varchar(200) NOT NULL,
    created_at                   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_premium_default_notice_outcome CHECK (outcome IS NULL OR outcome IN
        ('PAID','SUSPENDED','TERMINATED'))
);
CREATE INDEX ix_premium_default_notice_installment ON q360.premium_default_notice(tenant_id, installment_id);
"""

V006_CREATE_POLICY_ENDORSEMENT = """
CREATE TABLE q360.policy_endorsement (
    id                          uuid PRIMARY KEY,
    tenant_id                   uuid NOT NULL REFERENCES q360.tenant(id),
    policy_id                   uuid NOT NULL REFERENCES q360.policy(id),
    endorsement_number            integer NOT NULL,
    endorsement_type              varchar(30) NOT NULL,
    effective_date                date NOT NULL,
    payload_json                  jsonb NOT NULL DEFAULT '{}',
    created_by                    varchar(200) NOT NULL,
    created_at                    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_policy_endorsement_no UNIQUE (tenant_id, policy_id, endorsement_number),
    CONSTRAINT ck_policy_endorsement_type CHECK (endorsement_type IN
        ('ACTIVATE_MEMBER','ADD_MEMBER','EXCLUDE_MEMBER','CANCEL_POLICY')),
    CONSTRAINT ck_policy_endorsement_payload_json CHECK (jsonb_typeof(payload_json) = 'object')
);
CREATE INDEX ix_policy_endorsement_policy ON q360.policy_endorsement(tenant_id, policy_id, endorsement_number DESC);
"""

V007_CREATE_POLICY_STATE_HISTORY = """
CREATE TABLE q360.policy_state_history (
    id                          uuid PRIMARY KEY,
    tenant_id                   uuid NOT NULL REFERENCES q360.tenant(id),
    policy_id                   uuid NOT NULL REFERENCES q360.policy(id),
    from_status                  varchar(30),
    to_status                    varchar(30) NOT NULL,
    reason_code                  varchar(100),
    reason_text                  text,
    changed_by                   varchar(200) NOT NULL,
    changed_at                   timestamptz NOT NULL DEFAULT now(),
    correlation_id                varchar(100),
    CONSTRAINT ck_policy_history_to CHECK (to_status IN
        ('PENDING_FIRST_PREMIUM','ACTIVE','SUSPENDED','TERMINATED','CANCELLED','EXPIRED','RENEWED')),
    CONSTRAINT ck_policy_history_from CHECK (from_status IS NULL OR from_status IN
        ('PENDING_FIRST_PREMIUM','ACTIVE','SUSPENDED','TERMINATED','CANCELLED','EXPIRED','RENEWED'))
);
CREATE INDEX ix_policy_history ON q360.policy_state_history(tenant_id, policy_id, changed_at);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("foundation", "0001_foundation_baseline"),
        ("quote", "0004_product_version_optional"),
        ("product", "0002_plan_direct_to_product"),
        ("client", "0002_relationship_catalog"),
        ("eligibility", "0003_product_version_optional"),
    ]

    operations = [
        migrations.RunSQL(V001_CREATE_POLICY, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(V002_CREATE_POLICY_SIGNATURE, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(V003_CREATE_POLICY_MEMBER, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(V004_CREATE_PREMIUM_INSTALLMENT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(V005_CREATE_PREMIUM_DEFAULT_NOTICE, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(V006_CREATE_POLICY_ENDORSEMENT, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(V007_CREATE_POLICY_STATE_HISTORY, reverse_sql=migrations.RunSQL.noop),
    ]
