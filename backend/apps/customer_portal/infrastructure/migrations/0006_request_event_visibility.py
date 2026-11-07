"""Notas internas no atendimento: um evento do pedido pode ser só da equipa
(INTERNAL) e nunca aparece ao cliente no portal."""
from django.db import migrations, models

SQL = """
ALTER TABLE q360.portal_request_event ADD COLUMN IF NOT EXISTS visibility varchar(10) NOT NULL DEFAULT 'CUSTOMER';
ALTER TABLE q360.portal_request_event DROP CONSTRAINT IF EXISTS ck_portal_request_event_visibility;
ALTER TABLE q360.portal_request_event ADD CONSTRAINT ck_portal_request_event_visibility
    CHECK (visibility IN ('CUSTOMER','INTERNAL'));
"""

REVERSE = """
ALTER TABLE q360.portal_request_event DROP CONSTRAINT IF EXISTS ck_portal_request_event_visibility;
ALTER TABLE q360.portal_request_event DROP COLUMN IF EXISTS visibility;
"""


class Migration(migrations.Migration):
    dependencies = [("customer_portal", "0005_request_satisfaction")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=REVERSE)],
            state_operations=[
                migrations.AddField(
                    model_name="portalrequestevent", name="visibility",
                    field=models.CharField(default="CUSTOMER", max_length=10),
                ),
            ],
        ),
    ]
