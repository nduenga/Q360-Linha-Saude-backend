"""Adds `email`/`phone` to `proposer` (Product Owner decision, 2026-09-26:
"ao criar proponente tem de passar obrigatoriamente o email, telefone e
NIF" — NIF is already `registration_number`, added by V008/0001_client_baseline).

Pragmatic V1 addition, NOT part of ART-005/ART-012 — same posture as
0002_relationship_catalog.py. Columns are nullable at the DB level (a
handful of dev-tenant proposers already exist without them, and this
table has no backfill data to invent); `email`/`phone`/`registrationNumber`
are enforced as mandatory at the API boundary instead — see
apps/client/interfaces/serializers.py's ProposerCreateRequestSerializer.

Do not edit an already-applied migration (DOC-000 s3 P-08) — this is a
new file, not a change to 0001_client_baseline.py.
"""
from django.db import migrations

V0003_ADD_PROPOSER_CONTACT_FIELDS = """
ALTER TABLE q360.proposer
    ADD COLUMN email varchar(254),
    ADD COLUMN phone varchar(30);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("client", "0002_relationship_catalog"),
    ]

    operations = [
        migrations.RunSQL(sql=V0003_ADD_PROPOSER_CONTACT_FIELDS, reverse_sql=migrations.RunSQL.noop),
    ]
