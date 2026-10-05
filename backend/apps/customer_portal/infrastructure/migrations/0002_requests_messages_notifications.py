"""Portal Cliente — pedidos ao seguro, mensagens contextualizadas e
notificações (Portal_Cliente_Sistema_Cotacoes_Saude.pdf, secções 8, 14 e 15).

Nada disto está nos artefactos ART-005/ART-012; como a baseline do portal, é
esquema próprio e o DDL vive aqui (`managed = False` nos modelos).
"""
from django.db import migrations

V0002_CREATE = """
CREATE TABLE q360.portal_request (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    request_number      varchar(40) NOT NULL,
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    proposer_id         uuid NOT NULL REFERENCES q360.proposer(id),
    policy_id           uuid REFERENCES q360.policy(id),
    quote_id            uuid REFERENCES q360.quote(id),
    request_type        varchar(30) NOT NULL,
    subject             varchar(200) NOT NULL,
    description         text NOT NULL DEFAULT '',
    payload_json        jsonb NOT NULL DEFAULT '{}'::jsonb,
    status              varchar(30) NOT NULL DEFAULT 'OPEN',
    resolution_note     text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    row_version         bigint NOT NULL DEFAULT 0,
    CONSTRAINT uq_portal_request_number UNIQUE (tenant_id, request_number),
    CONSTRAINT ck_portal_request_status CHECK (status IN
        ('OPEN', 'IN_REVIEW', 'AWAITING_CUSTOMER', 'APPROVED', 'REJECTED', 'COMPLETED')),
    CONSTRAINT ck_portal_request_type CHECK (request_type IN
        ('DATA_CHANGE', 'MEMBER_INCLUSION', 'MEMBER_EXCLUSION', 'DOCUMENT_COPY', 'STATEMENT', 'CONTACT_CHANGE',
         'COVERAGE_QUESTION', 'RENEWAL', 'CANCELLATION', 'NEW_QUOTE', 'ACCEPT_QUOTE', 'OTHER'))
);
CREATE INDEX ix_portal_request_proposer ON q360.portal_request(tenant_id, proposer_id, created_at DESC);
CREATE INDEX ix_portal_request_status ON q360.portal_request(tenant_id, status, created_at);

CREATE TABLE q360.portal_request_event (
    id          uuid PRIMARY KEY,
    tenant_id   uuid NOT NULL REFERENCES q360.tenant(id),
    request_id  uuid NOT NULL REFERENCES q360.portal_request(id),
    from_status varchar(30),
    to_status   varchar(30) NOT NULL,
    note        text,
    actor_type  varchar(10) NOT NULL,
    actor_ref   varchar(200) NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_portal_request_event_actor CHECK (actor_type IN ('CUSTOMER', 'STAFF'))
);
CREATE INDEX ix_portal_request_event_request ON q360.portal_request_event(tenant_id, request_id, created_at);

CREATE TABLE q360.portal_message (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    proposer_id         uuid NOT NULL REFERENCES q360.proposer(id),
    context_type        varchar(10) NOT NULL,
    context_ref         varchar(100) NOT NULL,
    sender_type         varchar(10) NOT NULL,
    sender_ref          varchar(200) NOT NULL,
    body                text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    read_by_customer_at timestamptz,
    read_by_staff_at    timestamptz,
    CONSTRAINT ck_portal_message_context CHECK (context_type IN ('QUOTE', 'POLICY', 'REQUEST')),
    CONSTRAINT ck_portal_message_sender CHECK (sender_type IN ('CUSTOMER', 'STAFF'))
);
CREATE INDEX ix_portal_message_context ON q360.portal_message(tenant_id, context_type, context_ref, created_at);
CREATE INDEX ix_portal_message_proposer ON q360.portal_message(tenant_id, proposer_id, created_at DESC);

CREATE TABLE q360.portal_notification (
    id                  uuid PRIMARY KEY,
    tenant_id           uuid NOT NULL REFERENCES q360.tenant(id),
    customer_account_id uuid NOT NULL REFERENCES q360.customer_account(id),
    dedupe_key          varchar(200) NOT NULL,
    code                varchar(60) NOT NULL,
    title               varchar(200) NOT NULL,
    body                text NOT NULL DEFAULT '',
    link                varchar(300),
    created_at          timestamptz NOT NULL DEFAULT now(),
    read_at             timestamptz,
    CONSTRAINT uq_portal_notification_dedupe UNIQUE (tenant_id, customer_account_id, dedupe_key)
);
CREATE INDEX ix_portal_notification_account ON q360.portal_notification(tenant_id, customer_account_id, created_at DESC);
"""

V0002_DROP = """
DROP TABLE q360.portal_notification;
DROP TABLE q360.portal_message;
DROP TABLE q360.portal_request_event;
DROP TABLE q360.portal_request;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("customer_portal", "0001_customer_portal_baseline"),
        ("policy", "0001_policy_baseline"),
        ("quote", "0001_quote_baseline"),
    ]
    operations = [migrations.RunSQL(sql=V0002_CREATE, reverse_sql=V0002_DROP)]
