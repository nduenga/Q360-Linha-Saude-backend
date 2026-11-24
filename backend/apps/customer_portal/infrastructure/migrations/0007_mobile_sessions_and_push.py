"""App móvel do Portal do Cliente (roadmap_mobile.md, Fase 1): sessões por
dispositivo com token de renovação, dispositivos de notificações push e as
preferências de push por conta. Aditivo: o portal web não usa nada disto."""
from django.db import migrations, models

SQL = """
CREATE TABLE q360.customer_device_session (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    device_id           varchar(100) NOT NULL,
    device_name         varchar(120) NOT NULL DEFAULT '',
    platform            varchar(10) NOT NULL DEFAULT 'OTHER',
    app_version         varchar(30) NOT NULL DEFAULT '',
    token_hash          varchar(64) NOT NULL,
    previous_token_hash varchar(64),
    expires_at          timestamptz NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    last_used_at        timestamptz NOT NULL DEFAULT now(),
    revoked_at          timestamptz,
    revoked_reason      varchar(30),
    CONSTRAINT ck_customer_device_session_platform CHECK (platform IN ('IOS', 'ANDROID', 'WEB', 'OTHER'))
);
CREATE INDEX ix_customer_device_session_account
    ON q360.customer_device_session(tenant_id, customer_account_id, revoked_at);
CREATE INDEX ix_customer_device_session_device
    ON q360.customer_device_session(tenant_id, customer_account_id, device_id);

CREATE TABLE q360.customer_push_device (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    device_session_id   uuid REFERENCES q360.customer_device_session(id),
    expo_token          varchar(200) NOT NULL,
    platform            varchar(10) NOT NULL DEFAULT 'OTHER',
    active              boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_customer_push_device_token UNIQUE (tenant_id, expo_token),
    CONSTRAINT ck_customer_push_device_platform CHECK (platform IN ('IOS', 'ANDROID', 'WEB', 'OTHER'))
);
CREATE INDEX ix_customer_push_device_account
    ON q360.customer_push_device(tenant_id, customer_account_id, active);

ALTER TABLE q360.customer_account ADD COLUMN push_preferences jsonb NOT NULL DEFAULT '{}'::jsonb;
"""

REVERSE = """
ALTER TABLE q360.customer_account DROP COLUMN push_preferences;
DROP TABLE q360.customer_push_device;
DROP TABLE q360.customer_device_session;
"""


class Migration(migrations.Migration):
    dependencies = [("customer_portal", "0006_request_event_visibility")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=REVERSE)],
            state_operations=[
                migrations.AddField(
                    model_name="customeraccount", name="push_preferences",
                    field=models.JSONField(default=dict),
                ),
            ],
        ),
    ]
