"""Versões da cotação (R1): pontos de gravação imutáveis do estado editável
(data de início, escolhas, ajustes ACTIVE, população e decisões de
preexistência, e o prémio resultante), criados automaticamente quando o
estado muda ao recalcular e manualmente a pedido, com restauro. Forward-only."""
from django.db import migrations

V_VERSIONS = """
CREATE TABLE q360.quote_version (
    id             uuid PRIMARY KEY,
    tenant_id      uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id       uuid NOT NULL REFERENCES q360.quote(id) ON DELETE CASCADE,
    version_no     integer NOT NULL,
    source         varchar(30) NOT NULL,
    reason         text,
    snapshot_json  jsonb NOT NULL,
    checksum       varchar(64) NOT NULL,
    total_amount   numeric(30,8),
    currency_code  varchar(3),
    created_by     varchar(200) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_quote_version UNIQUE (tenant_id, quote_id, version_no),
    CONSTRAINT ck_quote_version_no CHECK (version_no > 0),
    CONSTRAINT ck_quote_version_source CHECK (source IN ('PRICED','MANUAL','RESTORED','RENEWAL','CLONE')),
    CONSTRAINT ck_quote_version_snapshot CHECK (jsonb_typeof(snapshot_json) = 'object')
);
CREATE INDEX ix_quote_version_quote ON q360.quote_version (tenant_id, quote_id, version_no DESC);
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0007_quote_scenarios")]

    operations = [migrations.RunSQL(V_VERSIONS, reverse_sql=migrations.RunSQL.noop)]
