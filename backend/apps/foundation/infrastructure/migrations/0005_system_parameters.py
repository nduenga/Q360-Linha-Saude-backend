"""Parâmetros globais do sistema editáveis pelo GTE (R7) com histórico
imutável (versionamento e rollback). Substitui o ecrã de parâmetros que o
frontend tinha só em memória. Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

V_SYSTEM_PARAMETERS = """
CREATE TABLE q360.system_parameter (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL REFERENCES q360.tenant(id),
    code          varchar(100) NOT NULL,
    value_json    jsonb NOT NULL,
    updated_by    varchar(200) NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    row_version   bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_system_parameter UNIQUE (tenant_id, code),
    CONSTRAINT ck_system_parameter_row_version CHECK (row_version >= 0)
);

CREATE TABLE q360.system_parameter_revision (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL REFERENCES q360.tenant(id),
    code          varchar(100) NOT NULL,
    revision_no   integer NOT NULL,
    action        varchar(30) NOT NULL,
    value_json    jsonb NOT NULL,
    reason        text,
    changed_by    varchar(200) NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_system_parameter_revision UNIQUE (tenant_id, code, revision_no),
    CONSTRAINT ck_system_parameter_revision_no CHECK (revision_no > 0)
);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0004_customer_actor_type")]

    operations = [migrations.RunSQL(V_SYSTEM_PARAMETERS, reverse_sql=migrations.RunSQL.noop)]
