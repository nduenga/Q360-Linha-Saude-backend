"""A cotação deixa de ter data de efeito (decisão de 2026-10-15).

Uma cotação ainda não é uma apólice: tem data de criação e validade
(`valid_until`, a partir do parâmetro configurável `quote.validity_days`);
o início da vigência decide-se na emissão da apólice. A data de referência
do cálculo passa a ser o dia de criação (`Quote.reference_date`).

A CHECK `ck_quote_dates` (validade ≥ data de efeito) cai com a coluna. O
reverso volta a criar a coluna com o dia de criação de cada cotação.
"""
from django.db import migrations

SQL = """
ALTER TABLE q360.quote DROP CONSTRAINT IF EXISTS ck_quote_dates;
ALTER TABLE q360.quote DROP COLUMN effective_date;
"""

REVERSE_SQL = """
ALTER TABLE q360.quote ADD COLUMN effective_date date;
UPDATE q360.quote SET effective_date = (created_at AT TIME ZONE 'UTC')::date;
ALTER TABLE q360.quote ALTER COLUMN effective_date SET NOT NULL;
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_dates CHECK (valid_until IS NULL OR valid_until >= effective_date);
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0012_quote_clone_source")]
    operations = [
        migrations.RunSQL(
            SQL,
            reverse_sql=REVERSE_SQL,
            state_operations=[migrations.RemoveField(model_name="quote", name="effective_date")],
        )
    ]
