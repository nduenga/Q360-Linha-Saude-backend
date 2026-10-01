"""Simulador GTE: escolhas da cotação, ajustes de prémio, doenças
preexistentes por membro e cotação de renovação.

- `quote.selection_json`: coberturas opcionais escolhidas, opção de
  participação A–E e alterações de capitais/participação "e se...".
- `quote.quote_type` / `source_policy_id`: cotação nova vs renovação
  (a apólice de origem fica só como referência, sem FK entre módulos).
- `quote_adjustment`: agravamentos/descontos com motivo, autor e remoção
  auditável (nunca se apaga uma linha: fica `REMOVED`).
- `quote_member.pre_existing_json`: tratamento de doença preexistente
  decidido para cada pessoa (6 opções do PDF).

Forward-only (`reverse_sql` no-op), como as restantes migrações.
"""
from django.db import migrations

V_SIMULATOR = """
ALTER TABLE q360.quote ADD COLUMN selection_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_selection_object CHECK (jsonb_typeof(selection_json) = 'object');
ALTER TABLE q360.quote ADD COLUMN quote_type varchar(20) NOT NULL DEFAULT 'NEW';
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_type CHECK (quote_type IN ('NEW','RENEWAL'));
ALTER TABLE q360.quote ADD COLUMN source_policy_id uuid;
ALTER TABLE q360.quote ADD COLUMN renewal_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_renewal_object CHECK (jsonb_typeof(renewal_json) = 'object');
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_renewal_source
    CHECK (quote_type = 'NEW' OR source_policy_id IS NOT NULL);

ALTER TABLE q360.quote_member ADD COLUMN pre_existing_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE q360.quote_member ADD CONSTRAINT ck_quote_member_pre_existing_object
    CHECK (jsonb_typeof(pre_existing_json) = 'object');

CREATE TABLE q360.quote_adjustment (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id         uuid NOT NULL REFERENCES q360.quote(id) ON DELETE CASCADE,
    kind             varchar(30) NOT NULL,
    value            numeric(30,8) NOT NULL,
    scope            varchar(20) NOT NULL,
    member_id        uuid REFERENCES q360.insured_member(id),
    reason           text NOT NULL,
    status           varchar(20) NOT NULL DEFAULT 'ACTIVE',
    impact_json      jsonb NOT NULL DEFAULT '{}'::jsonb,
    applied_by       varchar(200) NOT NULL,
    applied_at       timestamptz NOT NULL DEFAULT now(),
    removed_by       varchar(200),
    removed_at       timestamptz,
    removed_reason   text,
    CONSTRAINT ck_quote_adjustment_kind
        CHECK (kind IN ('SURCHARGE_PERCENT','DISCOUNT_PERCENT','SURCHARGE_AMOUNT','DISCOUNT_AMOUNT')),
    CONSTRAINT ck_quote_adjustment_value CHECK (value > 0),
    CONSTRAINT ck_quote_adjustment_scope CHECK (scope IN ('QUOTE','MEMBER')),
    CONSTRAINT ck_quote_adjustment_member CHECK ((scope = 'MEMBER') = (member_id IS NOT NULL)),
    CONSTRAINT ck_quote_adjustment_status CHECK (status IN ('ACTIVE','REMOVED')),
    CONSTRAINT ck_quote_adjustment_impact CHECK (jsonb_typeof(impact_json) = 'object')
);
CREATE INDEX ix_quote_adjustment_quote ON q360.quote_adjustment (tenant_id, quote_id, status);
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0005_bound_status")]

    operations = [
        migrations.RunSQL(V_SIMULATOR, reverse_sql=migrations.RunSQL.noop),
    ]
