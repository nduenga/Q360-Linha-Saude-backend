"""Add policy coverage changes to the endorsement type constraint."""
from django.db import migrations, models

ALTER_POLICY_ENDORSEMENT_TYPE = """
ALTER TABLE q360.policy_endorsement DROP CONSTRAINT ck_policy_endorsement_type;
ALTER TABLE q360.policy_endorsement ADD CONSTRAINT ck_policy_endorsement_type CHECK (endorsement_type IN
    ('ACTIVATE_MEMBER','ADD_MEMBER','CHANGE_COVERAGES','EXCLUDE_MEMBER','CANCEL_POLICY'));
"""


class Migration(migrations.Migration):
    dependencies = [("policy", "0003_initial")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    ALTER_POLICY_ENDORSEMENT_TYPE,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="policyendorsement",
                    name="endorsement_type",
                    field=models.CharField(
                        choices=[
                            ("ACTIVATE_MEMBER", "ACTIVATE_MEMBER"),
                            ("ADD_MEMBER", "ADD_MEMBER"),
                            ("CHANGE_COVERAGES", "CHANGE_COVERAGES"),
                            ("EXCLUDE_MEMBER", "EXCLUDE_MEMBER"),
                            ("CANCEL_POLICY", "CANCEL_POLICY"),
                        ],
                        max_length=30,
                    ),
                ),
            ],
        ),
    ]
