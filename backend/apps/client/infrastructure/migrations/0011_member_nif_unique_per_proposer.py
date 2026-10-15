"""NIF da pessoa segura único por tomador, não por tenant (2026-10-15).

A mesma pessoa pode estar segura em mais de um tomador (p.ex. colaborador de
uma empresa e titular de uma apólice individual) e ter o NIF nas duas fichas;
dentro do mesmo tomador o NIF continua a identificar uma só pessoa segura.
O NIF do proponente continua único por tenant (0010). Alarga a regra: não
há dados que deixem de a cumprir.
"""
from django.db import migrations

SQL = r"""
DROP INDEX q360.uq_insured_member_tenant_nif;
CREATE UNIQUE INDEX uq_insured_member_proposer_nif ON q360.insured_member (tenant_id, proposer_id, nif)
    WHERE nif IS NOT NULL;
"""

REVERSE_SQL = r"""
DROP INDEX q360.uq_insured_member_proposer_nif;
CREATE UNIQUE INDEX uq_insured_member_tenant_nif ON q360.insured_member (tenant_id, nif) WHERE nif IS NOT NULL;
"""


class Migration(migrations.Migration):
    dependencies = [("client", "0010_nif_unique_required")]
    operations = [migrations.RunSQL(SQL, reverse_sql=REVERSE_SQL)]
