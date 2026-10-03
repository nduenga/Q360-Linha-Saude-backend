"""Configuração de negócio versionada (tarifas, regras, textos) editável pela
interface. Cada versão tem ciclo DRAFT -> PENDING_APPROVAL -> PUBLISHED ->
RETIRED; o criador não pode aprovar. Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

SQL = """
CREATE TABLE q360.business_configuration (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL REFERENCES q360.tenant(id),
    config_key    varchar(120) NOT NULL,
    version_no    integer NOT NULL,
    effective_from date NOT NULL,
    effective_to  date,
    status        varchar(30) NOT NULL DEFAULT 'DRAFT',
    value_json    jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    checksum      varchar(128),
    created_by    varchar(200) NOT NULL,
    approved_by   varchar(200),
    published_by  varchar(200),
    submitted_at  timestamptz,
    approved_at   timestamptz,
    published_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    row_version   bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_business_configuration_version UNIQUE (tenant_id, config_key, version_no),
    CONSTRAINT ck_business_configuration_status
        CHECK (status IN ('DRAFT','PENDING_APPROVAL','PUBLISHED','RETIRED')),
    CONSTRAINT ck_business_configuration_period
        CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
CREATE INDEX ix_business_configuration_resolve
    ON q360.business_configuration (tenant_id, config_key, status, effective_from);

CREATE TABLE q360.business_configuration_document (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES q360.tenant(id),
    configuration_id uuid NOT NULL REFERENCES q360.business_configuration(id) ON DELETE CASCADE,
    document_type    varchar(80) NOT NULL,
    original_filename varchar(255) NOT NULL,
    content_type     varchar(120),
    storage_key      text NOT NULL,
    checksum         varchar(128),
    metadata_json    jsonb NOT NULL DEFAULT '{}'::jsonb,
    uploaded_by      varchar(200) NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0005_system_parameters")]
    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]
