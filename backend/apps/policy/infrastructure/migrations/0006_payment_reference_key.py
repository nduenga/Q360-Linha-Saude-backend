from django.db import migrations, models

SQL = """
ALTER TABLE q360.premium_installment ADD COLUMN payment_reference_key varchar(200);
CREATE UNIQUE INDEX uq_premium_installment_payment_reference
    ON q360.premium_installment(tenant_id, payment_reference_key)
    WHERE payment_reference_key IS NOT NULL AND status = 'PAID';
"""


class Migration(migrations.Migration):
    """Só os pagamentos novos preenchem a chave: o histórico fica intacto e uma
    repetição antiga nunca impede esta migração de correr."""

    dependencies = [("policy", "0005_merge_20261104_1223")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[migrations.AddField(
                model_name="premiuminstallment",
                name="payment_reference_key",
                field=models.CharField(blank=True, max_length=200, null=True),
            )],
        )
    ]
