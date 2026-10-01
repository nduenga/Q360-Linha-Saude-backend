"""Biblioteca de coberturas versionada + definição das coberturas + definições
de plano (PDF "Coberturas e Capitais", 1-Out-2026).

- `benefit.definition_json`: grupo, forma de garantia, sublimites típicos,
  participação e carências típicas, exclusões, listas fechadas (GTE edita).
- `benefit_revision`: histórico imutável (versionamento + rollback) de cada
  alteração a uma cobertura.
- `plan.settings_json`: segmento (Individual/Grupo), escalão, sistema de
  acesso, idades, regras de grupo, opção de participação, tratamento de
  doenças preexistentes... (ver `apps.product.domain.plan_settings`).
- `OUTPATIENT` (Ambulatório) deixa de ser cobertura BASE: no PDF é "O"
  (opcional) no Individual Base. Planos existentes mantêm-na associada.

Forward-only, como todas as migrações deste projecto (`reverse_sql` no-op).
"""
from django.db import migrations

V_BENEFIT_LIBRARY = """
ALTER TABLE q360.benefit ADD COLUMN definition_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE q360.benefit ADD CONSTRAINT ck_benefit_definition_object
    CHECK (jsonb_typeof(definition_json) = 'object');

UPDATE q360.benefit SET benefit_type = 'COMPLEMENTARY' WHERE code = 'OUTPATIENT';

CREATE TABLE q360.benefit_revision (
    id             uuid PRIMARY KEY,
    tenant_id      uuid NOT NULL REFERENCES q360.tenant(id),
    benefit_id     uuid NOT NULL REFERENCES q360.benefit(id),
    revision_no    integer NOT NULL,
    action         varchar(40) NOT NULL,
    snapshot_json  jsonb NOT NULL,
    reason         text,
    changed_by     varchar(200) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_benefit_revision UNIQUE (tenant_id, benefit_id, revision_no),
    CONSTRAINT ck_benefit_revision_no CHECK (revision_no > 0),
    CONSTRAINT ck_benefit_revision_snapshot CHECK (jsonb_typeof(snapshot_json) = 'object')
);
CREATE INDEX ix_benefit_revision_benefit ON q360.benefit_revision (tenant_id, benefit_id, revision_no DESC);

ALTER TABLE q360.plan ADD COLUMN settings_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE q360.plan ADD CONSTRAINT ck_plan_settings_object CHECK (jsonb_typeof(settings_json) = 'object');
"""


class Migration(migrations.Migration):
    dependencies = [("product", "0002_plan_direct_to_product")]

    operations = [
        migrations.RunSQL(V_BENEFIT_LIBRARY, reverse_sql=migrations.RunSQL.noop),
    ]
