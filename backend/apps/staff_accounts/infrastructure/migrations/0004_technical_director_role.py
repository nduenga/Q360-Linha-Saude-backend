from django.db import migrations


SQL = """
ALTER TABLE q360.staff_account_role DROP CONSTRAINT IF EXISTS ck_staff_account_role_valid;
ALTER TABLE q360.staff_account_role ADD CONSTRAINT ck_staff_account_role_valid
    CHECK (role IN ('ADMIN', 'SUBSCRIPTION_MANAGER', 'SUBSCRIBER', 'TECHNICAL_DIRECTOR'));
"""


class Migration(migrations.Migration):
    dependencies = [("staff_accounts", "0003_initial")]
    operations = [migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)]
