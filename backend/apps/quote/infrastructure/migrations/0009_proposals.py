"""Propostas (R8): formato (PDF/DOCX/HTML), cenário de origem, número de
proposta por cotação, nome e tipo do ficheiro. Os documentos antigos
(placeholder JSON) ficam com `format='JSON'`. Forward-only."""
from django.db import migrations

V_PROPOSALS = """
ALTER TABLE q360.document ADD COLUMN format varchar(10) NOT NULL DEFAULT 'JSON';
ALTER TABLE q360.document ADD CONSTRAINT ck_document_format CHECK (format IN ('JSON','PDF','DOCX','HTML'));
ALTER TABLE q360.document ADD COLUMN scenario_id uuid REFERENCES q360.quote_scenario(id) ON DELETE SET NULL;
ALTER TABLE q360.document ADD COLUMN content_type varchar(100);
ALTER TABLE q360.document ADD COLUMN file_name varchar(200);
ALTER TABLE q360.document ADD COLUMN proposal_no integer;
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0008_quote_versions")]

    operations = [migrations.RunSQL(V_PROPOSALS, reverse_sql=migrations.RunSQL.noop)]
