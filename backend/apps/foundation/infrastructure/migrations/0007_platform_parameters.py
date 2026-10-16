"""Camada de configuração geral do fornecedor: versões dos parâmetros que
valem para todos os tenants (estruturais, impostos legais e valores por
omissão dos operacionais), com aprovação por outra conta da plataforma e
vigência. Sem `tenant_id`. Forward-only (`reverse_sql` no-op)."""
import uuid

from django.db import migrations, models

SQL = """
CREATE TABLE q360.platform_parameter_version (
    id              uuid PRIMARY KEY,
    code            varchar(100) NOT NULL,
    version_no      integer NOT NULL,
    status          varchar(20) NOT NULL DEFAULT 'PENDING_APPROVAL',
    action          varchar(30) NOT NULL DEFAULT 'CREATED',
    value_json      jsonb NOT NULL,
    minimum_json    jsonb,
    maximum_json    jsonb,
    effective_from  timestamptz,
    reason          text NOT NULL,
    created_by      varchar(200) NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    decided_by      varchar(200),
    decided_at      timestamptz,
    decision_note   text,
    CONSTRAINT uq_platform_parameter_version UNIQUE (code, version_no),
    CONSTRAINT ck_platform_parameter_version_no CHECK (version_no > 0),
    CONSTRAINT ck_platform_parameter_status CHECK (status IN ('PENDING_APPROVAL','PUBLISHED','REJECTED')),
    CONSTRAINT ck_platform_parameter_four_eyes CHECK (decided_by IS NULL OR decided_by <> created_by)
);
CREATE INDEX ix_platform_parameter_in_effect ON q360.platform_parameter_version (code, status, effective_from);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0006_initial")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[
                migrations.CreateModel(
                    name="PlatformParameterVersion",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("code", models.CharField(max_length=100)),
                        ("version_no", models.IntegerField()),
                        ("status", models.CharField(default="PENDING_APPROVAL", max_length=20)),
                        ("action", models.CharField(default="CREATED", max_length=30)),
                        ("value_json", models.JSONField()),
                        ("minimum_json", models.JSONField(blank=True, null=True)),
                        ("maximum_json", models.JSONField(blank=True, null=True)),
                        ("effective_from", models.DateTimeField(blank=True, null=True)),
                        ("reason", models.TextField()),
                        ("created_by", models.CharField(max_length=200)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("decided_by", models.CharField(blank=True, max_length=200, null=True)),
                        ("decided_at", models.DateTimeField(blank=True, null=True)),
                        ("decision_note", models.TextField(blank=True, null=True)),
                    ],
                    options={"db_table": "platform_parameter_version", "managed": False},
                ),
            ],
        ),
    ]
