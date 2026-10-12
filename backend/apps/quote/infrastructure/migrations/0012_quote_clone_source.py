
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("quote", "0011_template_files"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE q360.quote
                    ADD COLUMN source_quote_id uuid NULL
                        REFERENCES q360.quote(id),
                    ADD COLUMN clone_reason text NOT NULL DEFAULT '';
            """,
            reverse_sql="""
                ALTER TABLE q360.quote
                    DROP COLUMN source_quote_id,
                    DROP COLUMN clone_reason;
            """,
            state_operations=[
                migrations.AddField(
                    model_name="quote",
                    name="source_quote",
                    field=models.ForeignKey(
                        to="quote.quote",
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cloned_quotes",
                        db_column="source_quote_id",
                    ),
                ),
                migrations.AddField(
                    model_name="quote",
                    name="clone_reason",
                    field=models.TextField(
                        blank=True,
                        default="",
                    ),
                ),
            ],
        ),
    ]
