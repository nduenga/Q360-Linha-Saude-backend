"""Customer portal baseline schema (ROADMAP_PORTAL_CLIENTE.md Fase 0).

Brand-new schema for a brand-new actor type (`actor_type='CUSTOMER'`,
see `apps/foundation/infrastructure/migrations/0004_customer_actor_type.py`)
— none of this is ART-005/ART-012, by design (ROADMAP_PORTAL_CLIENTE.md
intro: "é reflectido em código real, não só em intenção"). Depends on
`foundation` (tenant) and `client` (proposer) migrations for the FKs
below.
"""
from django.db import migrations

V0001_CREATE_CUSTOMER_PORTAL_SCHEMA = """
CREATE TABLE q360.customer_account (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    email               varchar(320) NOT NULL,
    email_verified      boolean NOT NULL DEFAULT false,
    failed_otp_attempts integer NOT NULL DEFAULT 0,
    locked_until        timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_customer_account_tenant_email UNIQUE (tenant_id, email)
);

CREATE TABLE q360.customer_account_proposer (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    proposer_id         uuid NOT NULL REFERENCES q360.proposer(id),
    linked_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_customer_account_proposer UNIQUE (tenant_id, customer_account_id, proposer_id)
);
CREATE INDEX ix_customer_account_proposer_proposer ON q360.customer_account_proposer(tenant_id, proposer_id);

CREATE TABLE q360.customer_login_challenge (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    otp_hash            varchar(200) NOT NULL,
    expires_at          timestamptz NOT NULL,
    consumed_at         timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_customer_login_challenge_account ON q360.customer_login_challenge(tenant_id, customer_account_id, created_at DESC);
"""

V0001_DROP_CUSTOMER_PORTAL_SCHEMA = """
DROP TABLE q360.customer_login_challenge;
DROP TABLE q360.customer_account_proposer;
DROP TABLE q360.customer_account;
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("foundation", "0001_foundation_baseline"),
        ("client", "0001_client_baseline"),
    ]
    operations = [
        migrations.RunSQL(sql=V0001_CREATE_CUSTOMER_PORTAL_SCHEMA, reverse_sql=V0001_DROP_CUSTOMER_PORTAL_SCHEMA),
    ]
