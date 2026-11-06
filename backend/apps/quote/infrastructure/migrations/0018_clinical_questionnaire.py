import uuid

from django.db import migrations, models

SQL = """
CREATE TABLE q360.clinical_questionnaire (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id uuid NOT NULL REFERENCES q360.quote(id) ON DELETE CASCADE,
    member_id uuid NOT NULL REFERENCES q360.insured_member(id),
    schema_version varchar(30) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'IN_PROGRESS',
    answers_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    current_section varchar(40),
    requested_from_customer_at timestamptz,
    requested_by varchar(200),
    updated_by varchar(200) NOT NULL,
    updated_channel varchar(20) NOT NULL DEFAULT 'STAFF',
    completed_at timestamptz,
    completed_by varchar(200),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    row_version bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_clinical_questionnaire_member UNIQUE (tenant_id, quote_id, member_id),
    CONSTRAINT ck_clinical_questionnaire_status CHECK (status IN ('IN_PROGRESS','COMPLETED')),
    CONSTRAINT ck_clinical_questionnaire_channel CHECK (updated_channel IN ('STAFF','CUSTOMER')),
    CONSTRAINT ck_clinical_questionnaire_answers CHECK (jsonb_typeof(answers_json) = 'object'),
    CONSTRAINT ck_clinical_questionnaire_completion CHECK (
        (status = 'COMPLETED' AND completed_at IS NOT NULL AND completed_by IS NOT NULL)
        OR (status = 'IN_PROGRESS' AND completed_at IS NULL AND completed_by IS NULL)
    ),
    CONSTRAINT ck_clinical_questionnaire_row_version CHECK (row_version >= 0)
);
CREATE INDEX ix_clinical_questionnaire_requested
    ON q360.clinical_questionnaire(tenant_id, requested_from_customer_at)
    WHERE requested_from_customer_at IS NOT NULL;
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0017_quote_version_endorsement_source"), ("client", "0001_client_baseline")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[migrations.CreateModel(
                name="ClinicalQuestionnaire",
                fields=[
                    ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                    ("schema_version", models.CharField(max_length=30)),
                    ("status", models.CharField(choices=[("IN_PROGRESS", "IN_PROGRESS"), ("COMPLETED", "COMPLETED")], default="IN_PROGRESS", max_length=20)),
                    ("answers_json", models.JSONField(default=dict)),
                    ("current_section", models.CharField(blank=True, max_length=40, null=True)),
                    ("requested_from_customer_at", models.DateTimeField(blank=True, null=True)),
                    ("requested_by", models.CharField(blank=True, max_length=200, null=True)),
                    ("updated_by", models.CharField(max_length=200)),
                    ("updated_channel", models.CharField(default="STAFF", max_length=20)),
                    ("completed_at", models.DateTimeField(blank=True, null=True)),
                    ("completed_by", models.CharField(blank=True, max_length=200, null=True)),
                    ("created_at", models.DateTimeField(auto_now_add=True)),
                    ("updated_at", models.DateTimeField(auto_now=True)),
                    ("row_version", models.BigIntegerField(default=0)),
                    ("member", models.ForeignKey(db_column="member_id", on_delete=models.DO_NOTHING, related_name="clinical_questionnaires", to="client.insuredmember")),
                    ("quote", models.ForeignKey(db_column="quote_id", on_delete=models.CASCADE, related_name="clinical_questionnaires", to="quote.quote")),
                    ("tenant", models.ForeignKey(db_column="tenant_id", on_delete=models.DO_NOTHING, to="foundation.tenant")),
                ],
                options={"db_table": "clinical_questionnaire", "managed": False},
            )],
        )
    ]
