"""Extends `ck_eligibility_decision` with the 3 new decisions produced by
the Angola category-rule engine (MOTOR_ELEGIBILIDADE.md secção 1, "Decisões
finais possíveis"): ELIGIBLE_WITH_LOADING, PENDING_DOCUMENT,
PENDING_MEDICAL_BOARD. None of these is a definitive rejection — the
frontend maps all three (and ELIGIBLE) to a non-red state, never
"Rejeitado"; only HARD_STOP is red.

`decision` widens from varchar(20) to varchar(30) because
'PENDING_MEDICAL_BOARD' (21 chars) does not fit the original width.

Do not edit 0001_eligibility_baseline.py (DOC-000 s3 P-08) — this is a
new file.
"""
from django.db import migrations

V0002_EXTEND_ELIGIBILITY_DECISION = """
ALTER TABLE q360.eligibility_evaluation
    ALTER COLUMN decision TYPE varchar(30);
ALTER TABLE q360.eligibility_evaluation
    DROP CONSTRAINT ck_eligibility_decision;
ALTER TABLE q360.eligibility_evaluation
    ADD CONSTRAINT ck_eligibility_decision CHECK (
        decision IN (
            'ELIGIBLE','WARNING','REFERRAL','HARD_STOP','CONFIG_ERROR',
            'ELIGIBLE_WITH_LOADING','PENDING_DOCUMENT','PENDING_MEDICAL_BOARD'
        )
    );
"""

V0002_REVERT_ELIGIBILITY_DECISION = """
ALTER TABLE q360.eligibility_evaluation
    DROP CONSTRAINT ck_eligibility_decision;
ALTER TABLE q360.eligibility_evaluation
    ADD CONSTRAINT ck_eligibility_decision CHECK (
        decision IN ('ELIGIBLE','WARNING','REFERRAL','HARD_STOP','CONFIG_ERROR')
    );
ALTER TABLE q360.eligibility_evaluation
    ALTER COLUMN decision TYPE varchar(20);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("eligibility", "0001_eligibility_baseline"),
    ]

    operations = [
        migrations.RunSQL(sql=V0002_EXTEND_ELIGIBILITY_DECISION, reverse_sql=V0002_REVERT_ELIGIBILITY_DECISION),
    ]
