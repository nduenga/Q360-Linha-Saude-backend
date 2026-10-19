import uuid
from django.db import migrations, models


SQL = """
CREATE TABLE q360.quote_discount_approval (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    quote_id uuid NOT NULL REFERENCES q360.quote(id) ON DELETE CASCADE,
    quote_row_version bigint NOT NULL,
    spec_json jsonb NOT NULL,
    reason text NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'PENDING',
    requested_by varchar(200) NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    decided_by varchar(200),
    decided_at timestamptz,
    decision_note text,
    adjustment_id uuid REFERENCES q360.quote_adjustment(id),
    impact_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_quote_discount_approval_status CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    CONSTRAINT ck_quote_discount_approval_spec CHECK (jsonb_typeof(spec_json) = 'object'),
    CONSTRAINT ck_quote_discount_approval_impact CHECK (jsonb_typeof(impact_json) = 'object'),
    CONSTRAINT ck_quote_discount_approval_decision CHECK (
        (status = 'PENDING' AND decided_by IS NULL AND decided_at IS NULL)
        OR (status <> 'PENDING' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)
    )
);
CREATE INDEX ix_quote_discount_approval_queue ON q360.quote_discount_approval(tenant_id, status, requested_at);
CREATE INDEX ix_quote_discount_approval_quote ON q360.quote_discount_approval(tenant_id, quote_id, requested_at DESC);
CREATE UNIQUE INDEX uq_quote_discount_pending_per_quote
    ON q360.quote_discount_approval(tenant_id, quote_id) WHERE status = 'PENDING';
"""


class Migration(migrations.Migration):
    dependencies = [("quote", "0013_drop_quote_effective_date")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)],
            state_operations=[migrations.CreateModel(
                name="QuoteDiscountApproval",
                fields=[
                    ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                    ("quote_row_version", models.BigIntegerField()),
                    ("spec_json", models.JSONField(default=dict)),
                    ("reason", models.TextField()),
                    ("status", models.CharField(choices=[("PENDING", "PENDING"), ("APPROVED", "APPROVED"), ("REJECTED", "REJECTED")], default="PENDING", max_length=20)),
                    ("requested_by", models.CharField(max_length=200)),
                    ("requested_at", models.DateTimeField(auto_now_add=True)),
                    ("decided_by", models.CharField(blank=True, max_length=200, null=True)),
                    ("decided_at", models.DateTimeField(blank=True, null=True)),
                    ("decision_note", models.TextField(blank=True, null=True)),
                    ("impact_json", models.JSONField(default=dict)),
                    ("adjustment", models.ForeignKey(blank=True, db_column="adjustment_id", null=True, on_delete=models.DO_NOTHING, to="quote.quoteadjustment")),
                    ("quote", models.ForeignKey(db_column="quote_id", on_delete=models.CASCADE, related_name="discount_approvals", to="quote.quote")),
                    ("tenant", models.ForeignKey(db_column="tenant_id", on_delete=models.DO_NOTHING, to="foundation.tenant")),
                ],
                options={"db_table": "quote_discount_approval", "managed": False},
            )],
        )
    ]
