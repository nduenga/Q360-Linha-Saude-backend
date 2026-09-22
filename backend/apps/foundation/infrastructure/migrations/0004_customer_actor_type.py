"""Extends `ck_audit_actor_type` with 'CUSTOMER' (ROADMAP_PORTAL_CLIENTE.md
Fase 0): a customer-portal actor's actions must be audited exactly like
staff/system/service actions are today. Do not edit
0001_foundation_baseline.py (DOC-000 s3 P-08) — this is a new file.
"""
from django.db import migrations

V0004_EXTEND_AUDIT_ACTOR_TYPE = """
ALTER TABLE q360.audit_event DROP CONSTRAINT ck_audit_actor_type;
ALTER TABLE q360.audit_event ADD CONSTRAINT ck_audit_actor_type
    CHECK (actor_type IN ('USER','SYSTEM','SERVICE','CUSTOMER'));
"""

V0004_REVERT_AUDIT_ACTOR_TYPE = """
ALTER TABLE q360.audit_event DROP CONSTRAINT ck_audit_actor_type;
ALTER TABLE q360.audit_event ADD CONSTRAINT ck_audit_actor_type
    CHECK (actor_type IN ('USER','SYSTEM','SERVICE'));
"""


class Migration(migrations.Migration):
    dependencies = [
        ("foundation", "0003_outbox_idempotency_consumer_inbox"),
    ]

    operations = [
        migrations.RunSQL(sql=V0004_EXTEND_AUDIT_ACTOR_TYPE, reverse_sql=V0004_REVERT_AUDIT_ACTOR_TYPE),
    ]
