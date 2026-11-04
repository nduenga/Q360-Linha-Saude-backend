from django.db import migrations, models

STATUS_CHOICES = [
    ("PENDING_FIRST_PREMIUM", "PENDING_FIRST_PREMIUM"),
    ("ACTIVE", "ACTIVE"),
    ("SUSPENDED", "SUSPENDED"),
    ("TERMINATED", "TERMINATED"),
    ("RESOLVED_BY_LAW", "RESOLVED_BY_LAW"),
    ("CANCELLED", "CANCELLED"),
    ("EXPIRED", "EXPIRED"),
    ("RENEWED", "RENEWED"),
]

FORWARD_SQL = """
ALTER TABLE q360.policy
    ADD COLUMN resolved_by_law boolean NOT NULL DEFAULT false,
    ADD COLUMN resolved_at timestamptz,
    ADD COLUMN resolved_effective_from date,
    ADD COLUMN resolution_reason_code varchar(50),
    ADD COLUMN legal_basis varchar(30);

ALTER TABLE q360.policy DROP CONSTRAINT ck_policy_status;
ALTER TABLE q360.policy ADD CONSTRAINT ck_policy_status CHECK (status IN
    ('PENDING_FIRST_PREMIUM','ACTIVE','SUSPENDED','TERMINATED','RESOLVED_BY_LAW','CANCELLED','EXPIRED','RENEWED'));
ALTER TABLE q360.policy ADD CONSTRAINT ck_policy_resolution CHECK (
    (status = 'RESOLVED_BY_LAW'
        AND resolved_by_law
        AND resolved_at IS NOT NULL
        AND resolved_effective_from IS NOT NULL
        AND ((resolution_reason_code = 'INITIAL_PREMIUM' AND legal_basis = 'ART_18_1')
            OR (resolution_reason_code = 'INSTALLMENT' AND legal_basis = 'ART_18_3')))
    OR
    (status <> 'RESOLVED_BY_LAW'
        AND NOT resolved_by_law
        AND resolved_at IS NULL
        AND resolved_effective_from IS NULL
        AND resolution_reason_code IS NULL
        AND legal_basis IS NULL)
);

ALTER TABLE q360.policy_state_history DROP CONSTRAINT ck_policy_history_to;
ALTER TABLE q360.policy_state_history ADD CONSTRAINT ck_policy_history_to CHECK (to_status IN
    ('PENDING_FIRST_PREMIUM','ACTIVE','SUSPENDED','TERMINATED','RESOLVED_BY_LAW','CANCELLED','EXPIRED','RENEWED'));
ALTER TABLE q360.policy_state_history DROP CONSTRAINT ck_policy_history_from;
ALTER TABLE q360.policy_state_history ADD CONSTRAINT ck_policy_history_from CHECK (from_status IS NULL OR from_status IN
    ('PENDING_FIRST_PREMIUM','ACTIVE','SUSPENDED','TERMINATED','RESOLVED_BY_LAW','CANCELLED','EXPIRED','RENEWED'));
"""

class Migration(migrations.Migration):
    dependencies = [("policy", "0003_initial")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(FORWARD_SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[
                migrations.AlterField(
                    model_name="policy",
                    name="status",
                    field=models.CharField(
                        choices=STATUS_CHOICES,
                        default="PENDING_FIRST_PREMIUM",
                        max_length=30,
                    ),
                ),
                migrations.AddField(
                    model_name="policy",
                    name="resolved_by_law",
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name="policy",
                    name="resolved_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="policy",
                    name="resolved_effective_from",
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="policy",
                    name="resolution_reason_code",
                    field=models.CharField(blank=True, max_length=50, null=True),
                ),
                migrations.AddField(
                    model_name="policy",
                    name="legal_basis",
                    field=models.CharField(blank=True, max_length=30, null=True),
                ),
            ],
        ),
    ]
