"""Modelos de partida do fornecedor (produto de mercado, modelo actuarial de
referência, conjuntos de fórmulas), versionados e aprovados por outra conta
da plataforma; cada tenant copia-os para rascunhos. Sem `tenant_id`.
Forward-only (`reverse_sql` no-op)."""
import uuid

from django.db import migrations, models

SQL = """
CREATE TABLE q360.platform_template_version (
    id              uuid PRIMARY KEY,
    code            varchar(60) NOT NULL,
    version_no      integer NOT NULL,
    status          varchar(20) NOT NULL DEFAULT 'PENDING_APPROVAL',
    kind            varchar(30) NOT NULL,
    name            varchar(200) NOT NULL,
    description     text,
    segment         varchar(20),
    content_json    jsonb NOT NULL,
    source          text,
    reason          text NOT NULL,
    created_by      varchar(200) NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    decided_by      varchar(200),
    decided_at      timestamptz,
    decision_note   text,
    CONSTRAINT uq_platform_template_version UNIQUE (code, version_no),
    CONSTRAINT ck_platform_template_no CHECK (version_no > 0),
    CONSTRAINT ck_platform_template_status CHECK (status IN ('PENDING_APPROVAL','PUBLISHED','REJECTED')),
    CONSTRAINT ck_platform_template_kind CHECK (kind IN ('PRODUCT','ACTUARIAL_MODEL','FORMULA_SET','COVERAGE_LIBRARY')),
    CONSTRAINT ck_platform_template_four_eyes CHECK (decided_by IS NULL OR decided_by <> created_by),
    CONSTRAINT ck_platform_template_content CHECK (jsonb_typeof(content_json) = 'object')
);
CREATE INDEX ix_platform_template_published ON q360.platform_template_version (code, status, version_no DESC);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0009_platform_reference_tables")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[
                migrations.CreateModel(
                    name="PlatformTemplateVersion",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("code", models.CharField(max_length=60)),
                        ("version_no", models.IntegerField()),
                        ("status", models.CharField(default="PENDING_APPROVAL", max_length=20)),
                        ("kind", models.CharField(max_length=30)),
                        ("name", models.CharField(max_length=200)),
                        ("description", models.TextField(blank=True, null=True)),
                        ("segment", models.CharField(blank=True, max_length=20, null=True)),
                        ("content_json", models.JSONField()),
                        ("source", models.TextField(blank=True, null=True)),
                        ("reason", models.TextField()),
                        ("created_by", models.CharField(max_length=200)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("decided_by", models.CharField(blank=True, max_length=200, null=True)),
                        ("decided_at", models.DateTimeField(blank=True, null=True)),
                        ("decision_note", models.TextField(blank=True, null=True)),
                    ],
                    options={"db_table": "platform_template_version", "managed": False},
                ),
            ],
        ),
    ]
