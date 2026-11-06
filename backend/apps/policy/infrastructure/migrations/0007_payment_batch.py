from django.db import migrations, models

SQL = """
ALTER TABLE q360.premium_installment ADD COLUMN payment_batch_id uuid;
CREATE INDEX ix_premium_installment_payment_batch
    ON q360.premium_installment(tenant_id, payment_batch_id)
    WHERE payment_batch_id IS NOT NULL;
"""


class Migration(migrations.Migration):
    """Liga as prestações pagas pela mesma transferência."""

    dependencies = [("policy", "0006_payment_reference_key")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[migrations.AddField(
                model_name="premiuminstallment",
                name="payment_batch_id",
                field=models.UUIDField(blank=True, null=True),
            )],
        )
    ]
