"""Cenários de cotação (R5): conjuntos de parâmetros (coberturas opcionais,
opção A–E, capitais "e se...", ajustes) comparáveis lado a lado, com o
resultado do cálculo guardado e um único cenário "selecionado" por cotação
(o que gera a proposta). Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

V_SCENARIOS = """
CREATE TABLE q360.quote_scenario (
    id                    uuid PRIMARY KEY,
    tenant_id             uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id              uuid NOT NULL REFERENCES q360.quote(id) ON DELETE CASCADE,
    name                  varchar(200) NOT NULL,
    description           text,
    parameters_json       jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_json           jsonb NOT NULL DEFAULT '{}'::jsonb,
    inputs_hash           varchar(64),
    base_scenario_id      uuid REFERENCES q360.quote_scenario(id) ON DELETE SET NULL,
    is_selected           boolean NOT NULL DEFAULT false,
    created_by            varchar(200) NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    row_version           bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_quote_scenario_name UNIQUE (tenant_id, quote_id, name),
    CONSTRAINT ck_quote_scenario_params CHECK (jsonb_typeof(parameters_json) = 'object'),
    CONSTRAINT ck_quote_scenario_result CHECK (jsonb_typeof(result_json) = 'object'),
    CONSTRAINT ck_quote_scenario_row_version CHECK (row_version >= 0)
);
CREATE UNIQUE INDEX uq_quote_scenario_selected ON q360.quote_scenario (tenant_id, quote_id) WHERE is_selected;
CREATE INDEX ix_quote_scenario_quote ON q360.quote_scenario (tenant_id, quote_id, created_at);
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0006_simulator_selection_adjustments")]

    operations = [migrations.RunSQL(V_SCENARIOS, reverse_sql=migrations.RunSQL.noop)]
