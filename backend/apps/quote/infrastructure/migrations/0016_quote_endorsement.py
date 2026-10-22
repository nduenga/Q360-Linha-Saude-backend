"""Cotação de endosso (inclusão de pessoas numa apólice ativa a meio do
período): tipo `ENDORSEMENT`, sempre ligado à apólice (`source_policy_id`), e
os dados próprios do endosso (data de inclusão, cálculo pro-rata congelado,
prazo de aceitação do cliente) em `endorsement_json`."""
from django.db import migrations, models

SQL = """
ALTER TABLE q360.quote DROP CONSTRAINT IF EXISTS ck_quote_type;
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_type CHECK (quote_type IN ('NEW','RENEWAL','ENDORSEMENT'));
ALTER TABLE q360.quote ADD COLUMN IF NOT EXISTS endorsement_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_endorsement_object CHECK (jsonb_typeof(endorsement_json) = 'object');
CREATE INDEX IF NOT EXISTS ix_quote_source_policy_type ON q360.quote (source_policy_id, quote_type)
    WHERE source_policy_id IS NOT NULL;
"""

REVERSE = """
DROP INDEX IF EXISTS q360.ix_quote_source_policy_type;
ALTER TABLE q360.quote DROP CONSTRAINT IF EXISTS ck_quote_endorsement_object;
ALTER TABLE q360.quote DROP COLUMN IF EXISTS endorsement_json;
ALTER TABLE q360.quote DROP CONSTRAINT IF EXISTS ck_quote_type;
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_type CHECK (quote_type IN ('NEW','RENEWAL'));
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0015_quote_source_channel")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=REVERSE)],
            state_operations=[migrations.AddField(
                model_name="quote", name="endorsement_json", field=models.JSONField(default=dict),
            )],
        ),
    ]
