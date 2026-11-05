"""Os endossos gravam uma versão da cotação com source='ENDORSEMENT', valor que
a constraint original não aceitava: aceitar a alteração de coberturas dava erro 500."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("quote", "0016_quote_endorsement")]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE q360.quote_version DROP CONSTRAINT IF EXISTS ck_quote_version_source;
            ALTER TABLE q360.quote_version ADD CONSTRAINT ck_quote_version_source
                CHECK (source IN ('PRICED','MANUAL','RESTORED','RENEWAL','CLONE','ENDORSEMENT'));
            """,
            reverse_sql="""
            ALTER TABLE q360.quote_version DROP CONSTRAINT IF EXISTS ck_quote_version_source;
            ALTER TABLE q360.quote_version ADD CONSTRAINT ck_quote_version_source
                CHECK (source IN ('PRICED','MANUAL','RESTORED','RENEWAL','CLONE'));
            """,
        ),
    ]
