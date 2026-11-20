"""Gestão das seguradoras e auditoria da plataforma.

- `tenant.settings_json`: definições geridas pela plataforma (suspensão com
  motivo e data de reativação, identidade visual, limites e módulos).
- `platform_audit_event.tenant_id`: a seguradora a que o evento diz respeito,
  para filtrar e exportar a auditoria por seguradora.
- `platform_template_version.effective_from`: vigência dos modelos do fornecedor.
Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

SQL = """
ALTER TABLE q360.tenant ADD COLUMN IF NOT EXISTS settings_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE q360.platform_audit_event ADD COLUMN IF NOT EXISTS tenant_id uuid NULL;
CREATE INDEX IF NOT EXISTS ix_platform_audit_event_tenant ON q360.platform_audit_event (tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_platform_audit_event_occurred ON q360.platform_audit_event (occurred_at DESC);
ALTER TABLE q360.platform_template_version ADD COLUMN IF NOT EXISTS effective_from timestamptz NULL;
UPDATE q360.platform_template_version SET effective_from = COALESCE(decided_at, created_at)
 WHERE status = 'PUBLISHED' AND effective_from IS NULL;
"""


class Migration(migrations.Migration):
    dependencies = [("platform_admin", "0003_initial"), ("foundation", "0010_platform_templates")]
    operations = [migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)]
