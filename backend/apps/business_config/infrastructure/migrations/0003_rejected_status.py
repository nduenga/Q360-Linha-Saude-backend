"""Estado REJECTED na configuração de negócio.

A versão rejeitada pelo aprovador fica REJECTED (com o motivo nos metadados
e na auditoria) até o autor a corrigir: editar volta a DRAFT; também pode ser
reenviada para aprovação sem alterações."""
from django.db import migrations, models

SQL = """
ALTER TABLE q360.business_configuration DROP CONSTRAINT ck_business_configuration_status;
ALTER TABLE q360.business_configuration ADD CONSTRAINT ck_business_configuration_status
    CHECK (status IN ('DRAFT','PENDING_APPROVAL','REJECTED','PUBLISHED','RETIRED'));
"""

REVERSE_SQL = """
UPDATE q360.business_configuration SET status = 'DRAFT' WHERE status = 'REJECTED';
ALTER TABLE q360.business_configuration DROP CONSTRAINT ck_business_configuration_status;
ALTER TABLE q360.business_configuration ADD CONSTRAINT ck_business_configuration_status
    CHECK (status IN ('DRAFT','PENDING_APPROVAL','PUBLISHED','RETIRED'));
"""


class Migration(migrations.Migration):
    dependencies = [("business_config", "0002_initial")]
    operations = [
        migrations.RunSQL(SQL, reverse_sql=REVERSE_SQL),
        migrations.AlterField(
            model_name="businessconfiguration",
            name="status",
            field=models.CharField(
                choices=[("DRAFT", "DRAFT"), ("PENDING_APPROVAL", "PENDING_APPROVAL"), ("REJECTED", "REJECTED"),
                         ("PUBLISHED", "PUBLISHED"), ("RETIRED", "RETIRED")],
                default="DRAFT", max_length=30,
            ),
        ),
    ]
