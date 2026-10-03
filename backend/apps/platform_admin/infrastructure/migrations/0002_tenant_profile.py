"""Dados da empresa cliente no tenant (razão social, NIF, contactos, morada).
Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

SQL = """
ALTER TABLE q360.tenant ADD COLUMN IF NOT EXISTS profile_json jsonb NOT NULL DEFAULT '{}'::jsonb;
"""


class Migration(migrations.Migration):
    dependencies = [("platform_admin", "0001_platform_admin")]
    operations = [migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)]
