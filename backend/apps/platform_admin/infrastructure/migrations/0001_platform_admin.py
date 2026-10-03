from django.db import migrations

SQL = """
CREATE TABLE q360.platform_admin (
 id uuid PRIMARY KEY, email varchar(320) NOT NULL UNIQUE, name varchar(200) NOT NULL,
 password_hash varchar(200) NOT NULL, status varchar(20) NOT NULL DEFAULT 'ACTIVE',
 failed_login_attempts integer NOT NULL DEFAULT 0, locked_until timestamptz, last_login_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT ck_platform_admin_status CHECK (status IN ('ACTIVE','DISABLED'))
);
CREATE TABLE q360.platform_audit_event (
 id uuid PRIMARY KEY, actor_id varchar(200) NOT NULL, action varchar(120) NOT NULL,
 entity_type varchar(120) NOT NULL, entity_id varchar(200), occurred_at timestamptz NOT NULL DEFAULT now(),
 correlation_id varchar(100), metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
 CONSTRAINT ck_platform_audit_metadata_object CHECK (jsonb_typeof(metadata_json) = 'object')
);
CREATE INDEX ix_platform_audit_occurred ON q360.platform_audit_event(occurred_at DESC);
CREATE INDEX ix_platform_audit_entity ON q360.platform_audit_event(entity_type, entity_id);
CREATE INDEX ix_platform_audit_actor ON q360.platform_audit_event(actor_id, occurred_at DESC);
"""

class Migration(migrations.Migration):
    initial = True
    dependencies = [("foundation", "0001_foundation_baseline"), ("staff_accounts", "0001_staff_accounts_baseline")]
    operations = [migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop)]
