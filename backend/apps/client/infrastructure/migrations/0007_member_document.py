"""Documentos de suporte das pessoas seguras (certificado de matrícula, prova
de união, prova de dependência…): envio, análise e decisão.

Esquema próprio (não existe em ART-005/ART-012); `managed = False` no modelo.
"""
import uuid

from django.db import migrations, models

CREATE = """
CREATE TABLE q360.member_document (
    id                 uuid PRIMARY KEY,
    tenant_id          uuid NOT NULL REFERENCES q360.tenant(id),
    member_id          uuid NOT NULL REFERENCES q360.insured_member(id),
    evidence_type      varchar(40) NOT NULL,
    status             varchar(20) NOT NULL DEFAULT 'SUBMITTED',
    original_filename  varchar(255) NOT NULL,
    content_type       varchar(100) NOT NULL,
    size_bytes         bigint NOT NULL,
    checksum           varchar(128) NOT NULL,
    storage_key        text NOT NULL,
    metadata_json      jsonb NOT NULL DEFAULT '{}'::jsonb,
    note               text,
    submitted_by_type  varchar(10) NOT NULL,
    submitted_by_ref   varchar(200) NOT NULL,
    submitted_at       timestamptz NOT NULL DEFAULT now(),
    reviewed_by        varchar(200),
    reviewed_at        timestamptz,
    review_note        text,
    CONSTRAINT ck_member_document_status CHECK (status IN ('SUBMITTED', 'APPROVED', 'REJECTED')),
    CONSTRAINT ck_member_document_evidence CHECK (evidence_type IN
        ('ENROLLMENT_CERTIFICATE', 'UNION_HOMOLOGATION', 'DEPENDENCY_PROOF', 'OTHER')),
    CONSTRAINT ck_member_document_submitter CHECK (submitted_by_type IN ('CUSTOMER', 'STAFF'))
);
CREATE INDEX ix_member_document_member ON q360.member_document(tenant_id, member_id, submitted_at DESC);
CREATE INDEX ix_member_document_status ON q360.member_document(tenant_id, status, submitted_at);
"""

DROP = "DROP TABLE q360.member_document;"


class Migration(migrations.Migration):

    dependencies = [
        ("client", "0006_proposer_address"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE, reverse_sql=DROP),
        migrations.CreateModel(
            name="MemberDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("evidence_type", models.CharField(max_length=40)),
                ("status", models.CharField(default="SUBMITTED", max_length=20)),
                ("original_filename", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=100)),
                ("size_bytes", models.BigIntegerField()),
                ("checksum", models.CharField(max_length=128)),
                ("storage_key", models.TextField()),
                ("metadata_json", models.JSONField(default=dict)),
                ("note", models.TextField(blank=True, null=True)),
                ("submitted_by_type", models.CharField(max_length=10)),
                ("submitted_by_ref", models.CharField(max_length=200)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_by", models.CharField(blank=True, max_length=200, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.TextField(blank=True, null=True)),
            ],
            options={"db_table": "member_document", "managed": False},
        ),
    ]
