"""Tabelas de referência do fornecedor (províncias, tabelas de mercado),
versionadas e aprovadas por outra conta da plataforma; os tenants usam-nas
nas fórmulas com `tabela("codigo", chave, "coluna")`. Sem `tenant_id`.
Forward-only (`reverse_sql` no-op)."""
import uuid

from django.db import migrations, models

SQL = """
CREATE TABLE q360.platform_reference_table_version (
    id              uuid PRIMARY KEY,
    code            varchar(60) NOT NULL,
    version_no      integer NOT NULL,
    status          varchar(20) NOT NULL DEFAULT 'PENDING_APPROVAL',
    name            varchar(200) NOT NULL,
    description     text,
    key_column      varchar(60) NOT NULL,
    columns_json    jsonb NOT NULL,
    rows_json       jsonb NOT NULL,
    source          text,
    effective_from  timestamptz,
    reason          text NOT NULL,
    created_by      varchar(200) NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    decided_by      varchar(200),
    decided_at      timestamptz,
    decision_note   text,
    CONSTRAINT uq_platform_reference_table_version UNIQUE (code, version_no),
    CONSTRAINT ck_platform_reference_table_no CHECK (version_no > 0),
    CONSTRAINT ck_platform_reference_table_status CHECK (status IN ('PENDING_APPROVAL','PUBLISHED','REJECTED')),
    CONSTRAINT ck_platform_reference_table_four_eyes CHECK (decided_by IS NULL OR decided_by <> created_by),
    CONSTRAINT ck_platform_reference_table_columns CHECK (jsonb_typeof(columns_json) = 'array'),
    CONSTRAINT ck_platform_reference_table_rows CHECK (jsonb_typeof(rows_json) = 'array')
);
CREATE INDEX ix_platform_reference_table_in_effect ON q360.platform_reference_table_version (code, status, effective_from);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0008_platform_parameter_source")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[
                migrations.CreateModel(
                    name="PlatformReferenceTableVersion",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("code", models.CharField(max_length=60)),
                        ("version_no", models.IntegerField()),
                        ("status", models.CharField(default="PENDING_APPROVAL", max_length=20)),
                        ("name", models.CharField(max_length=200)),
                        ("description", models.TextField(blank=True, null=True)),
                        ("key_column", models.CharField(max_length=60)),
                        ("columns_json", models.JSONField()),
                        ("rows_json", models.JSONField()),
                        ("source", models.TextField(blank=True, null=True)),
                        ("effective_from", models.DateTimeField(blank=True, null=True)),
                        ("reason", models.TextField()),
                        ("created_by", models.CharField(max_length=200)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("decided_by", models.CharField(blank=True, max_length=200, null=True)),
                        ("decided_at", models.DateTimeField(blank=True, null=True)),
                        ("decision_note", models.TextField(blank=True, null=True)),
                    ],
                    options={"db_table": "platform_reference_table_version", "managed": False},
                ),
            ],
        ),
    ]
