"""Use employee as the organisational household anchor, not TITULAR."""
from django.db import migrations


SQL = r"""
ALTER TABLE q360.relationship_code DROP CONSTRAINT IF EXISTS ck_relationship_category;
ALTER TABLE q360.relationship_code ADD CONSTRAINT ck_relationship_category CHECK (
    category IN ('TITULAR','COLLABORATOR','SPOUSE','CHILD','DESCENDANT','ASCENDANT','OTHER')
);

-- Legacy organisational TITULAR entries represented employees. Individual
-- proposers keep TITULAR as their own household anchor.
UPDATE q360.insured_member m
SET relationship_code = 'COLABORADOR', row_version = m.row_version + 1, updated_at = now()
FROM q360.proposer p
WHERE p.id = m.proposer_id AND p.proposer_type = 'ORGANISATION'
  AND m.relationship_code = 'TITULAR';

UPDATE q360.family_household_member hm
SET relationship_code = 'COLABORADOR'
FROM q360.insured_member m
WHERE hm.member_id = m.id AND m.relationship_code = 'COLABORADOR'
  AND hm.relationship_code = 'TITULAR';
"""


class Migration(migrations.Migration):
    dependencies = [("client", "0018_person_household_identity")]
    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]
