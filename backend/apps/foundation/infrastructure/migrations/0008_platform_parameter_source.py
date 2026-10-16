"""Fonte legal das versões da camada geral: o diploma ou norma que fixa um
valor legal (selo, ARSEG, maioridade) e uma ligação opcional para o texto.
Forward-only (`reverse_sql` no-op)."""
from django.db import migrations, models

SQL = """
ALTER TABLE q360.platform_parameter_version
    ADD COLUMN IF NOT EXISTS legal_reference text,
    ADD COLUMN IF NOT EXISTS source_url varchar(500);
"""


class Migration(migrations.Migration):
    dependencies = [("foundation", "0007_platform_parameters")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[
                migrations.AddField(
                    model_name="platformparameterversion", name="legal_reference",
                    field=models.TextField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="platformparameterversion", name="source_url",
                    field=models.CharField(blank=True, max_length=500, null=True),
                ),
            ],
        ),
    ]
