"""Real, DB-backed relationship-code catalog (ROADMAP_ANGOLA_CUSTOMIZATION.md
OD-003 / OPEN_DECISIONS.md#S03-RELATIONSHIP-001, Product Owner decision
2026-09-21).

Pragmatic V1 addition, NOT part of ART-005/ART-012 (unlike `benefit`,
which ART-012 V006 already defined) — `insured_member.relationship_code`
(V009) stays exactly as it is, a plain `varchar(40)`. This new table gives
that free-text value a real, listable source of truth instead of a value
hardcoded in the frontend, mirroring the `benefit` catalog pattern from
Épico 1 (apps/product/infrastructure/migrations, V006).

Do not edit an already-applied migration (DOC-000 s3 P-08) — this is a
new file, not a change to 0001_client_baseline.py.
"""
from django.db import migrations

V0002_CREATE_RELATIONSHIP_CODE = """
CREATE TABLE q360.relationship_code (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    code                varchar(40) NOT NULL,
    label               varchar(100) NOT NULL,
    category            varchar(20) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_relationship_code UNIQUE (tenant_id, code),
    CONSTRAINT ck_relationship_category CHECK (
        category IN ('TITULAR','SPOUSE','CHILD','ASCENDANT','OTHER')
    )
);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("client", "0001_client_baseline"),
    ]

    operations = [
        migrations.RunSQL(sql=V0002_CREATE_RELATIONSHIP_CODE, reverse_sql=migrations.RunSQL.noop),
    ]
