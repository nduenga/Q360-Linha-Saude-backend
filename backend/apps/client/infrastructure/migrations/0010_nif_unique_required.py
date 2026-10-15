"""NIF obrigatório por tipo de cliente e único por tenant (decisão R1, 2026-10-14).

- Proponente: NIF obrigatório, no formato do tipo (INDIVIDUAL = 9 dígitos +
  2 letras + 3 dígitos; ORGANISATION = 10 dígitos) e único por tenant.
- Pessoa segura: NIF opcional (um menor pode não ter), mas, quando existe,
  no formato de pessoa singular e único por tenant.

As CHECK de obrigatoriedade/formato por tipo são `NOT VALID`: valem para
todas as linhas novas e alteradas, sem rejeitar a migração por registos
antigos sem NIF (esses têm de ser completados na próxima edição). A
unicidade não pode ser parcial: se já houver NIF repetidos a migração pára
com a lista, para serem corrigidos antes — nunca se apaga nem altera dados.
"""
from django.db import migrations

SQL = r"""
DO $$
DECLARE duplicates text;
BEGIN
    SELECT string_agg(format('%s (%s)', nif, n), ', ') INTO duplicates
    FROM (SELECT nif, count(*) AS n FROM q360.proposer WHERE nif IS NOT NULL
          GROUP BY tenant_id, nif HAVING count(*) > 1) d;
    IF duplicates IS NOT NULL THEN
        RAISE EXCEPTION 'NIF de proponente repetido no mesmo tenant: %. Corrija antes de migrar.', duplicates;
    END IF;
    SELECT string_agg(format('%s (%s)', nif, n), ', ') INTO duplicates
    FROM (SELECT nif, count(*) AS n FROM q360.insured_member WHERE nif IS NOT NULL
          GROUP BY tenant_id, nif HAVING count(*) > 1) d;
    IF duplicates IS NOT NULL THEN
        RAISE EXCEPTION 'NIF de pessoa segura repetido no mesmo tenant: %. Corrija antes de migrar.', duplicates;
    END IF;
END $$;

DROP INDEX IF EXISTS q360.ix_proposer_nif;
CREATE UNIQUE INDEX uq_proposer_tenant_nif ON q360.proposer (tenant_id, nif) WHERE nif IS NOT NULL;
ALTER TABLE q360.proposer ADD CONSTRAINT ck_proposer_nif_by_type CHECK (
    nif IS NOT NULL AND (
        (proposer_type = 'INDIVIDUAL' AND nif ~ '^\d{9}[A-Z]{2}\d{3}$')
        OR (proposer_type = 'ORGANISATION' AND nif ~ '^\d{10}$')
    )
) NOT VALID;

CREATE UNIQUE INDEX uq_insured_member_tenant_nif ON q360.insured_member (tenant_id, nif) WHERE nif IS NOT NULL;
ALTER TABLE q360.insured_member ADD CONSTRAINT ck_insured_member_nif_format
    CHECK (nif IS NULL OR nif ~ '^\d{9}[A-Z]{2}\d{3}$');
"""

REVERSE_SQL = r"""
ALTER TABLE q360.insured_member DROP CONSTRAINT ck_insured_member_nif_format;
DROP INDEX q360.uq_insured_member_tenant_nif;
ALTER TABLE q360.proposer DROP CONSTRAINT ck_proposer_nif_by_type;
DROP INDEX q360.uq_proposer_tenant_nif;
CREATE INDEX ix_proposer_nif ON q360.proposer (tenant_id, nif) WHERE nif IS NOT NULL;
"""


class Migration(migrations.Migration):
    dependencies = [("client", "0009_member_nif")]
    operations = [migrations.RunSQL(SQL, reverse_sql=REVERSE_SQL)]
