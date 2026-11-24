"""App móvel, fases 3 e 4 (roadmap_mobile.md): rede convencionada de
prestadores, eventos de uso da app, idioma do cliente e marca de conta
apagada (exigência das lojas)."""
from django.db import migrations, models

SQL = """
CREATE TABLE q360.care_provider (
    id              uuid PRIMARY KEY,
    tenant_id       uuid NOT NULL REFERENCES q360.tenant(id),
    name            varchar(200) NOT NULL,
    provider_type   varchar(20) NOT NULL DEFAULT 'CLINIC',
    specialties     jsonb NOT NULL DEFAULT '[]'::jsonb,
    province        varchar(80) NOT NULL DEFAULT '',
    municipality    varchar(80) NOT NULL DEFAULT '',
    address         varchar(300) NOT NULL DEFAULT '',
    phone           varchar(40) NOT NULL DEFAULT '',
    opening_hours   varchar(200) NOT NULL DEFAULT '',
    emergency       boolean NOT NULL DEFAULT false,
    latitude        numeric(9,6),
    longitude       numeric(9,6),
    active          boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_care_provider_type CHECK (provider_type IN
        ('HOSPITAL', 'CLINIC', 'LAB', 'PHARMACY', 'IMAGING', 'DENTAL', 'OTHER')),
    CONSTRAINT ck_care_provider_coords CHECK (
        (latitude IS NULL AND longitude IS NULL) OR
        (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180))
);
CREATE INDEX ix_care_provider_tenant ON q360.care_provider(tenant_id, active, province);

CREATE TABLE q360.portal_usage_event (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    name                varchar(40) NOT NULL,
    screen              varchar(80) NOT NULL DEFAULT '',
    platform            varchar(10) NOT NULL DEFAULT 'OTHER',
    app_version         varchar(30) NOT NULL DEFAULT '',
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_portal_usage_event_tenant ON q360.portal_usage_event(tenant_id, name, created_at);

ALTER TABLE q360.customer_account ADD COLUMN language varchar(5) NOT NULL DEFAULT 'pt';
ALTER TABLE q360.customer_account ADD COLUMN deleted_at timestamptz;
"""

REVERSE = """
ALTER TABLE q360.customer_account DROP COLUMN deleted_at;
ALTER TABLE q360.customer_account DROP COLUMN language;
DROP TABLE q360.portal_usage_event;
DROP TABLE q360.care_provider;
"""


class Migration(migrations.Migration):
    dependencies = [("customer_portal", "0007_mobile_sessions_and_push")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, reverse_sql=REVERSE)],
            state_operations=[
                migrations.AddField(model_name="customeraccount", name="language",
                                    field=models.CharField(default="pt", max_length=5)),
                migrations.AddField(model_name="customeraccount", name="deleted_at",
                                    field=models.DateTimeField(null=True, blank=True)),
            ],
        ),
    ]
