"""Modelos de documento com ficheiros: papel timbrado em PDF (opção A) e modelo
Word com marcas {{variável}} (opção B), e o tipo de documento a que se aplicam
(proposta ou apólice).

Esquema próprio; `managed = False` no modelo.
"""
from django.db import migrations, models

UP = """
ALTER TABLE q360.document_template_version
    ADD COLUMN document_type  varchar(20) NOT NULL DEFAULT 'QUOTE_PROPOSAL',
    ADD COLUMN letterhead_key text,
    ADD COLUMN letterhead_name varchar(255),
    ADD COLUMN word_key       text,
    ADD COLUMN word_name      varchar(255),
    ADD COLUMN settings_json  jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD CONSTRAINT ck_template_document_type CHECK (document_type IN ('QUOTE_PROPOSAL', 'POLICY'));
"""

DOWN = """
ALTER TABLE q360.document_template_version
    DROP CONSTRAINT ck_template_document_type,
    DROP COLUMN document_type,
    DROP COLUMN letterhead_key,
    DROP COLUMN letterhead_name,
    DROP COLUMN word_key,
    DROP COLUMN word_name,
    DROP COLUMN settings_json;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("quote", "0010_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=UP, reverse_sql=DOWN),
        migrations.AddField("documenttemplateversion", "document_type", models.CharField(default="QUOTE_PROPOSAL", max_length=20)),
        migrations.AddField("documenttemplateversion", "letterhead_key", models.TextField(blank=True, null=True)),
        migrations.AddField("documenttemplateversion", "letterhead_name", models.CharField(blank=True, max_length=255, null=True)),
        migrations.AddField("documenttemplateversion", "word_key", models.TextField(blank=True, null=True)),
        migrations.AddField("documenttemplateversion", "word_name", models.CharField(blank=True, max_length=255, null=True)),
        migrations.AddField("documenttemplateversion", "settings_json", models.JSONField(default=dict)),
    ]
