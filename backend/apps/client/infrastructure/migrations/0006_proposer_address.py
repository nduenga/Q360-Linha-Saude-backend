from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("client", "0005_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE q360.proposer
                ADD COLUMN address varchar(500);
            """,
            reverse_sql="""
                ALTER TABLE q360.proposer
                DROP COLUMN address;
            """,
        ),
    ]