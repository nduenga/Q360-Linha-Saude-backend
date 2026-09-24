"""Staff accounts baseline schema - self-hosted replacement for the
external Auth0 IdP. Brand-new schema, not ART-005/ART-012 (staff identity
was previously entirely external, no approved document defines it), same
posture as apps/customer_portal/infrastructure/migrations/0001_*.py.
Depends on foundation's `tenant` table for the FK below.
"""
from django.db import migrations

V0001_CREATE_STAFF_ACCOUNTS_SCHEMA = """
CREATE TABLE q360.staff_account (
    id                     uuid PRIMARY KEY,
    tenant_id              uuid NOT NULL REFERENCES q360.tenant(id),
    email                  varchar(320) NOT NULL,
    name                   varchar(200) NOT NULL,
    password_hash          varchar(200) NOT NULL,
    status                 varchar(20) NOT NULL DEFAULT 'ACTIVE',
    failed_login_attempts  integer NOT NULL DEFAULT 0,
    locked_until           timestamptz,
    last_login_at          timestamptz,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    row_version            bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_staff_account_tenant_email UNIQUE (tenant_id, email),
    CONSTRAINT ck_staff_account_status CHECK (status IN ('ACTIVE', 'DISABLED'))
);

CREATE TABLE q360.staff_account_role (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    staff_account_id    uuid NOT NULL REFERENCES q360.staff_account(id),
    role                varchar(30) NOT NULL,
    assigned_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_staff_account_role UNIQUE (tenant_id, staff_account_id, role),
    CONSTRAINT ck_staff_account_role_valid CHECK (
        role IN ('ADMIN', 'PRODUCT_CONFIGURATOR', 'SUBSCRIBER', 'APPROVER', 'AUDITOR')
    )
);
CREATE INDEX ix_staff_account_role_account ON q360.staff_account_role(tenant_id, staff_account_id);

CREATE TABLE q360.staff_refresh_token (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    staff_account_id    uuid NOT NULL REFERENCES q360.staff_account(id),
    token_hash          varchar(200) NOT NULL,
    expires_at          timestamptz NOT NULL,
    revoked_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_staff_refresh_token_account ON q360.staff_refresh_token(tenant_id, staff_account_id, revoked_at);
"""

V0001_DROP_STAFF_ACCOUNTS_SCHEMA = """
DROP TABLE q360.staff_refresh_token;
DROP TABLE q360.staff_account_role;
DROP TABLE q360.staff_account;
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("foundation", "0001_foundation_baseline"),
    ]
    operations = [
        migrations.RunSQL(sql=V0001_CREATE_STAFF_ACCOUNTS_SCHEMA, reverse_sql=V0001_DROP_STAFF_ACCOUNTS_SCHEMA),
    ]
