from django.db import migrations


class Migration(migrations.Migration):
    """Data de nascimento do proponente individual (obrigatória na API;
    nula em empresas e em registos antigos, que passam a ter de a preencher
    na próxima edição)."""

    dependencies = [
        ("client", "0007_member_document"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE q360.proposer ADD COLUMN date_of_birth date;",
            reverse_sql="ALTER TABLE q360.proposer DROP COLUMN date_of_birth;",
        ),
    ]
