"""Adds `BOUND` to `quote.status` (DECISIONS_TAKEN.md#S09-POLICY-001,
ROADMAP_APOLICES.md Fase 2) — a Quote that has produced a `Policy`
(`apps.policy`) is terminal, distinct from `APPROVED`. Widens
`ck_quote_status`/`ck_quote_history_to`/`ck_quote_history_from`
(0001_quote_baseline.py) without editing that baseline, same forward-only
policy as every other migration in this project.
"""
from django.db import migrations

_STATUSES = "'DRAFT','READY','IN_REVIEW','APPROVED','REJECTED','EXPIRED','CANCELLED','BOUND'"

V029_QUOTE_BOUND_STATUS = f"""
ALTER TABLE q360.quote DROP CONSTRAINT ck_quote_status;
ALTER TABLE q360.quote ADD CONSTRAINT ck_quote_status CHECK (status IN ({_STATUSES}));

ALTER TABLE q360.quote_state_history DROP CONSTRAINT ck_quote_history_to;
ALTER TABLE q360.quote_state_history ADD CONSTRAINT ck_quote_history_to CHECK (to_status IN ({_STATUSES}));

ALTER TABLE q360.quote_state_history DROP CONSTRAINT ck_quote_history_from;
ALTER TABLE q360.quote_state_history ADD CONSTRAINT ck_quote_history_from
    CHECK (from_status IS NULL OR from_status IN ({_STATUSES}));
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0004_product_version_optional")]

    operations = [
        migrations.RunSQL(V029_QUOTE_BOUND_STATUS, reverse_sql=migrations.RunSQL.noop),
    ]
