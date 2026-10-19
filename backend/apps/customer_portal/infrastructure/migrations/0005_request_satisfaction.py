import uuid
from django.db import migrations, models


V0005_CREATE = """
CREATE TABLE q360.portal_request_satisfaction (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES q360.tenant(id),
    request_id uuid NOT NULL REFERENCES q360.portal_request(id),
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    score smallint NOT NULL,
    comment text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_portal_request_satisfaction UNIQUE (tenant_id, request_id),
    CONSTRAINT ck_portal_request_satisfaction_score CHECK (score >= 0)
);
CREATE INDEX ix_portal_request_satisfaction_tenant_created
    ON q360.portal_request_satisfaction(tenant_id, created_at DESC);
"""

V0005_DROP = "DROP TABLE q360.portal_request_satisfaction;"


class Migration(migrations.Migration):
    dependencies = [("customer_portal", "0004_initial")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(sql=V0005_CREATE, reverse_sql=V0005_DROP)],
            state_operations=[migrations.CreateModel(
                name="PortalRequestSatisfaction",
                fields=[
                    ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                    ("score", models.PositiveSmallIntegerField()),
                    ("comment", models.TextField(blank=True, default="")),
                    ("created_at", models.DateTimeField(auto_now_add=True)),
                    ("customer_account", models.ForeignKey(db_column="customer_account_id", on_delete=models.DO_NOTHING, to="customer_portal.customeraccount")),
                    ("request", models.ForeignKey(db_column="request_id", on_delete=models.DO_NOTHING, to="customer_portal.portalrequest")),
                    ("tenant", models.ForeignKey(db_column="tenant_id", on_delete=models.DO_NOTHING, to="foundation.tenant")),
                ],
                options={"db_table": "portal_request_satisfaction", "managed": False},
            )],
        )
    ]
