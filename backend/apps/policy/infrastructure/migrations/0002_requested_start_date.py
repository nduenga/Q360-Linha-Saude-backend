"""Adds `policy.requested_start_date` (ROADMAP_APOLICES.md Fase 3,
OD-APO-003) — the tomador's requested vigência start, validated at
issuance against the Quote's `effectiveDate` and the signature date
(apps.policy.application.issuance_service), and used at activation as a
floor over the default "day after signature/payment" rule. Forward-only
(reverse_sql is a deliberate no-op, same policy as every other migration
in this project).
"""
from django.db import migrations

V008_POLICY_REQUESTED_START_DATE = """
ALTER TABLE q360.policy ADD COLUMN requested_start_date date;
"""


class Migration(migrations.Migration):
    dependencies = [("policy", "0001_policy_baseline")]

    operations = [
        migrations.RunSQL(V008_POLICY_REQUESTED_START_DATE, reverse_sql=migrations.RunSQL.noop),
    ]
