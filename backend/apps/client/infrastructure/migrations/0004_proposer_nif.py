"""Add the canonical AGT NIF to proposers.

`registration_number` pre-dates the explicit NIF field and was frequently
used for it. Valid legacy values are backfilled; values that are not an AGT
NIF remain only as registration numbers, so this migration never invents or
mislabels an identifier. A non-unique index preserves pre-existing duplicate
legacy data; the service prevents new duplicates after normalisation.
"""
from django.db import migrations


V0004_ADD_PROPOSER_NIF = r"""
ALTER TABLE q360.proposer
    ADD COLUMN nif varchar(14);

UPDATE q360.proposer
SET nif = upper(regexp_replace(registration_number, '\s+', '', 'g'))
WHERE registration_number IS NOT NULL
  AND upper(regexp_replace(registration_number, '\s+', '', 'g'))
      ~ '^(\d{10}|\d{9}[A-Z]{2}\d{3})$';

ALTER TABLE q360.proposer
    ADD CONSTRAINT ck_proposer_nif_agt_format
    CHECK (
        nif IS NULL
        OR nif ~ '^(\d{10}|\d{9}[A-Z]{2}\d{3})$'
    );

CREATE INDEX ix_proposer_nif
    ON q360.proposer(tenant_id, nif)
    WHERE nif IS NOT NULL;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("client", "0003_proposer_contact_fields"),
    ]

    operations = [
        migrations.RunSQL(sql=V0004_ADD_PROPOSER_NIF, reverse_sql=migrations.RunSQL.noop),
    ]
