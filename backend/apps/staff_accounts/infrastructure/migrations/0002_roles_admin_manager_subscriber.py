"""Perfis do tenant: ADMIN, SUBSCRIPTION_MANAGER (gestor de subscricao) e
SUBSCRIBER. O Configurador de Produto, o Aprovador e o Auditor passam a
Gestor de subscricao (que reune o que os tres faziam). Contas que tinham
varios destes ficam com um so. Forward-only (`reverse_sql` no-op)."""
from django.db import migrations

SQL = """
ALTER TABLE q360.staff_account_role DROP CONSTRAINT IF EXISTS ck_staff_account_role_valid;

-- Uma conta com varios perfis legados (ou ja com o novo) fica com uma so linha.
DELETE FROM q360.staff_account_role r
WHERE r.role IN ('PRODUCT_CONFIGURATOR', 'APPROVER', 'AUDITOR')
  AND EXISTS (
      SELECT 1 FROM q360.staff_account_role k
      WHERE k.tenant_id = r.tenant_id AND k.staff_account_id = r.staff_account_id AND k.id <> r.id
        AND (k.role = 'SUBSCRIPTION_MANAGER'
             OR (k.role IN ('PRODUCT_CONFIGURATOR', 'APPROVER', 'AUDITOR') AND k.id < r.id))
  );

UPDATE q360.staff_account_role SET role = 'SUBSCRIPTION_MANAGER'
WHERE role IN ('PRODUCT_CONFIGURATOR', 'APPROVER', 'AUDITOR');

ALTER TABLE q360.staff_account_role ADD CONSTRAINT ck_staff_account_role_valid
    CHECK (role IN ('ADMIN', 'SUBSCRIPTION_MANAGER', 'SUBSCRIBER'));
"""


class Migration(migrations.Migration):
    dependencies = [("staff_accounts", "0001_staff_accounts_baseline")]
    operations = [migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)]
