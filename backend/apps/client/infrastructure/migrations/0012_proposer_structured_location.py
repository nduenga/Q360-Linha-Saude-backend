"""Optional structured geography for proposers; existing free-text address remains intact."""
from django.db import migrations


SQL = """
ALTER TABLE q360.proposer
    ADD COLUMN province varchar(100),
    ADD COLUMN municipality varchar(100);
"""

REVERSE_SQL = """
ALTER TABLE q360.proposer
    DROP COLUMN municipality,
    DROP COLUMN province;
"""


class Migration(migrations.Migration):
    dependencies = [("client", "0011_member_nif_unique_per_proposer")]
    operations = [migrations.RunSQL(SQL, reverse_sql=REVERSE_SQL)]
