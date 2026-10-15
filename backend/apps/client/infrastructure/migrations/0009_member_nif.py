from django.db import migrations


class Migration(migrations.Migration):
    """NIF opcional da pessoa segura (beneficiário). Sem unicidade: nenhuma
    regra de negócio a define e um menor pode não ter NIF."""

    dependencies = [
        ("client", "0008_proposer_date_of_birth"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE q360.insured_member ADD COLUMN nif varchar(14);",
            reverse_sql="ALTER TABLE q360.insured_member DROP COLUMN nif;",
        ),
    ]
