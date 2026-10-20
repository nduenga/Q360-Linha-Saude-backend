"""Persist the acquisition channel reported at quote creation.

The value is intentionally nullable and not an enum: channel vocabularies
belong to each distribution integration and legacy quotes have no reliable
source attribution.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quote", "0014_quote_discount_approval")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(
                "ALTER TABLE q360.quote ADD COLUMN source_channel varchar(60);",
                reverse_sql="ALTER TABLE q360.quote DROP COLUMN source_channel;",
            )],
            state_operations=[migrations.AddField(
                model_name="quote",
                name="source_channel",
                field=models.CharField(blank=True, max_length=60, null=True),
            )],
        ),
    ]
