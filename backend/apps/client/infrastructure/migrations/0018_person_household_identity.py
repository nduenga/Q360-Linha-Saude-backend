"""Separate a person's civil identity from a company's insured population."""
from django.db import migrations


SQL = r"""
CREATE TABLE IF NOT EXISTS q360.person (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    first_name varchar(120) NOT NULL,
    last_name varchar(120),
    date_of_birth date,
    sex_code varchar(20),
    nif varchar(14),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    row_version bigint NOT NULL DEFAULT 0
);

ALTER TABLE q360.insured_member ADD COLUMN IF NOT EXISTS person_id uuid;
UPDATE q360.insured_member SET person_id = gen_random_uuid() WHERE person_id IS NULL;
INSERT INTO q360.person (id, tenant_id, first_name, last_name, date_of_birth, sex_code, nif)
SELECT m.person_id, m.tenant_id, COALESCE(NULLIF(m.first_name, ''), 'Pessoa'), m.last_name,
       m.date_of_birth, m.sex_code, m.nif
FROM q360.insured_member m
WHERE NOT EXISTS (SELECT 1 FROM q360.person p WHERE p.id = m.person_id);
ALTER TABLE q360.insured_member ADD CONSTRAINT fk_insured_member_person
    FOREIGN KEY (person_id) REFERENCES q360.person(id);
CREATE INDEX IF NOT EXISTS ix_insured_member_person ON q360.insured_member(tenant_id, person_id);

ALTER TABLE q360.family_household ADD COLUMN IF NOT EXISTS primary_person_id uuid;
UPDATE q360.family_household h SET primary_person_id = m.person_id
FROM q360.insured_member m WHERE m.id = h.primary_member_id AND h.primary_person_id IS NULL;
ALTER TABLE q360.family_household ADD CONSTRAINT fk_family_household_primary_person
    FOREIGN KEY (primary_person_id) REFERENCES q360.person(id);

ALTER TABLE q360.family_household_member ADD COLUMN IF NOT EXISTS person_id uuid;
ALTER TABLE q360.family_household_member ADD COLUMN IF NOT EXISTS relationship_code varchar(40);
UPDATE q360.family_household_member hm SET person_id = m.person_id, relationship_code = m.relationship_code
FROM q360.insured_member m WHERE m.id = hm.member_id AND hm.person_id IS NULL;
ALTER TABLE q360.family_household_member ALTER COLUMN member_id DROP NOT NULL;
ALTER TABLE q360.family_household_member ADD CONSTRAINT fk_household_member_person
    FOREIGN KEY (person_id) REFERENCES q360.person(id);
ALTER TABLE q360.family_household_member ADD CONSTRAINT ck_household_member_identity
    CHECK (member_id IS NOT NULL OR person_id IS NOT NULL);
CREATE INDEX IF NOT EXISTS ix_household_member_person ON q360.family_household_member(tenant_id, person_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_household_active_person
    ON q360.family_household_member(tenant_id, household_id, person_id)
    WHERE person_id IS NOT NULL AND left_at IS NULL;
"""


class Migration(migrations.Migration):
    dependencies = [("client", "0017_repair_family_household_tables")]
    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]
