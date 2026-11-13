from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quote", "0018_clinical_questionnaire")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE q360.clinical_questionnaire "
                    "ADD COLUMN IF NOT EXISTS schema_json jsonb NOT NULL DEFAULT '{}'::jsonb;"
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="clinicalquestionnaire",
                    name="schema_json",
                    field=models.JSONField(default=dict),
                )
            ],
        )
    ]
