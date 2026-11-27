"""Servidor SMTP configurado no painel: uma linha global (tenant_id nulo) e,
opcionalmente, uma por seguradora. A palavra-passe fica cifrada (Fernet).
Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

SQL = """
CREATE TABLE IF NOT EXISTS q360.email_settings (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NULL REFERENCES q360.tenant(id),
    host             varchar(255) NOT NULL,
    port             integer NOT NULL DEFAULT 587,
    security         varchar(10) NOT NULL DEFAULT 'STARTTLS',
    username         varchar(320) NOT NULL DEFAULT '',
    password_enc     text NOT NULL DEFAULT '',
    from_address     varchar(320) NOT NULL,
    from_name        varchar(200) NOT NULL DEFAULT '',
    reply_to         varchar(320) NOT NULL DEFAULT '',
    timeout_seconds  integer NOT NULL DEFAULT 20,
    enabled          boolean NOT NULL DEFAULT true,
    last_test_at     timestamptz NULL,
    last_test_ok     boolean NULL,
    last_test_error  text NOT NULL DEFAULT '',
    updated_by       varchar(200) NOT NULL DEFAULT '',
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_email_settings_security CHECK (security IN ('STARTTLS', 'SSL', 'NONE'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_email_settings_scope
    ON q360.email_settings ((COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid)));
"""


class Migration(migrations.Migration):
    dependencies = [("platform_admin", "0004_tenant_settings_audit_tenant")]
    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.CreateModel(
            name="EmailSettings",
            fields=[],
            options={"db_table": "email_settings", "managed": False},
        ),
    ]
