"""Sinistralidade (R2): importações de sinistros e de prémios do cliente
(inclui o histórico de 3 anos pedido na transferência de outra seguradora),
conjuntos de premissas de projeção e projeções calculadas. Dados de saúde:
o beneficiário é só uma referência pseudonimizada (`member_reference`).
Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

V_CLAIMS = """
CREATE TABLE q360.claims_import (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL REFERENCES q360.tenant(id),
    kind          varchar(10) NOT NULL,
    proposer_id   uuid NOT NULL REFERENCES q360.proposer(id),
    policy_id     uuid,
    source        varchar(40) NOT NULL DEFAULT 'INTERNAL',
    file_name     varchar(250) NOT NULL,
    total_rows    integer NOT NULL,
    imported_rows integer NOT NULL,
    error_rows    integer NOT NULL,
    errors_json   jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by    varchar(200) NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_claims_import_kind CHECK (kind IN ('CLAIMS','PREMIUMS')),
    CONSTRAINT ck_claims_import_source CHECK (source IN ('INTERNAL','OTHER_INSURER'))
);

CREATE TABLE q360.claim_record (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES q360.tenant(id),
    import_id        uuid NOT NULL REFERENCES q360.claims_import(id) ON DELETE CASCADE,
    proposer_id      uuid NOT NULL REFERENCES q360.proposer(id),
    policy_id        uuid,
    member_reference varchar(100),
    occurrence_date  date NOT NULL,
    benefit_code     varchar(60) NOT NULL,
    paid_amount      numeric(30,8) NOT NULL,
    provision_amount numeric(30,8) NOT NULL DEFAULT 0,
    currency_code    varchar(3) NOT NULL,
    status           varchar(20) NOT NULL DEFAULT 'PAID',
    CONSTRAINT ck_claim_amounts CHECK (paid_amount >= 0 AND provision_amount >= 0),
    CONSTRAINT ck_claim_status CHECK (status IN ('PAID','OPEN','REJECTED'))
);
CREATE INDEX ix_claim_record_scope ON q360.claim_record (tenant_id, proposer_id, occurrence_date);

CREATE TABLE q360.premium_record (
    id             uuid PRIMARY KEY,
    tenant_id      uuid NOT NULL REFERENCES q360.tenant(id),
    import_id      uuid NOT NULL REFERENCES q360.claims_import(id) ON DELETE CASCADE,
    proposer_id    uuid NOT NULL REFERENCES q360.proposer(id),
    policy_id      uuid,
    period_start   date NOT NULL,
    period_end     date NOT NULL,
    premium_amount numeric(30,8) NOT NULL,
    insured_count  integer,
    currency_code  varchar(3) NOT NULL,
    CONSTRAINT ck_premium_period CHECK (period_end >= period_start),
    CONSTRAINT ck_premium_amount CHECK (premium_amount >= 0),
    CONSTRAINT ck_premium_insured CHECK (insured_count IS NULL OR insured_count > 0)
);
CREATE INDEX ix_premium_record_scope ON q360.premium_record (tenant_id, proposer_id, period_start);

CREATE TABLE q360.projection_assumption_set (
    id           uuid PRIMARY KEY,
    tenant_id    uuid NOT NULL REFERENCES q360.tenant(id),
    name         varchar(200) NOT NULL,
    params_json  jsonb NOT NULL,
    created_by   varchar(200) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_projection_assumption_name UNIQUE (tenant_id, name),
    CONSTRAINT ck_projection_assumption_params CHECK (jsonb_typeof(params_json) = 'object')
);

CREATE TABLE q360.projection_run (
    id                 uuid PRIMARY KEY,
    tenant_id          uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id        uuid NOT NULL REFERENCES q360.proposer(id),
    policy_id          uuid,
    assumption_set_id  uuid REFERENCES q360.projection_assumption_set(id) ON DELETE SET NULL,
    params_json        jsonb NOT NULL,
    result_json        jsonb NOT NULL,
    created_by         varchar(200) NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0005_system_parameters"), ("client", "0004_proposer_nif")]

    operations = [migrations.RunSQL(V_CLAIMS, reverse_sql=migrations.RunSQL.noop)]
