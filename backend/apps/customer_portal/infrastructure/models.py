"""ORM adapters for the customer portal's own physical schema
(ROADMAP_PORTAL_CLIENTE.md Fase 0) — a brand-new schema, not part of
ART-005/ART-012 (this actor type does not exist in any approved Q360
document yet). `managed = False` for the same reason as every other
module (DOC-000 s3 P-08): the real DDL lives in
`infrastructure/migrations/0001_customer_portal_baseline.py`, this is
just the ORM's view of it. All models inherit `TenantScopedModel`
(Q360-S1-04) — tenant isolation applies to a customer's own data exactly
like it does to staff's.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.client.infrastructure.models import Proposer
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel


class CustomerAccount(TenantScopedModel):
    """OD-PORTAL-002 (Product Owner decision 2026-09-22): many-to-one via
    NIF — one account can aggregate several `Proposer` rows of the same
    tenant over time (see `CustomerAccountProposer`). Deliberately does
    NOT duplicate `Proposer.registration_number`/`display_name`: this
    table only holds what is needed to authenticate, per
    ROADMAP_PORTAL_CLIENTE.md Fase 0."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    email = models.EmailField(max_length=320)
    email_verified = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=256, null=True, blank=True)
    password_set_at = models.DateTimeField(null=True, blank=True)
    failed_otp_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "customer_account"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.email} ({self.id})"


class CustomerAccountProposer(TenantScopedModel):
    """Join table backing OD-PORTAL-002's many-to-one link. A row here is
    created the first time a `CustomerAccount` successfully authenticates
    against a given `Proposer` (via matching quoteNumber +
    registrationNumber) — never created speculatively."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    customer_account = models.ForeignKey(
        CustomerAccount, on_delete=models.DO_NOTHING, db_column="customer_account_id", related_name="proposer_links"
    )
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "customer_account_proposer"


class CustomerLoginChallenge(TenantScopedModel):
    """One issued email-OTP challenge (OD-PORTAL-001: email OTP only).
    `otp_hash` is hashed with Django's own password hasher
    (`django.contrib.auth.hashers`) — never stored or logged in clear
    text. A challenge is single-use (`consumed_at`) and short-lived
    (`expires_at`, `settings.CUSTOMER_PORTAL_OTP_TTL_SECONDS`)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    customer_account = models.ForeignKey(
        CustomerAccount, on_delete=models.DO_NOTHING, db_column="customer_account_id", related_name="login_challenges"
    )
    otp_hash = models.CharField(max_length=200)
    purpose = models.CharField(max_length=20, default="LOGIN")
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "customer_login_challenge"


class PortalRequest(TenantScopedModel):
    """Pedido do cliente ao seguro (PDF s.8). O cliente pede, o backoffice
    analisa e decide — o estado só muda por `requests_service`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    request_number = models.CharField(max_length=40)
    customer_account = models.ForeignKey(CustomerAccount, on_delete=models.DO_NOTHING, db_column="customer_account_id")
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    policy = models.ForeignKey(
        "policy.Policy", on_delete=models.DO_NOTHING, db_column="policy_id", null=True, blank=True, related_name="+"
    )
    quote = models.ForeignKey(
        "quote.Quote", on_delete=models.DO_NOTHING, db_column="quote_id", null=True, blank=True, related_name="+"
    )
    request_type = models.CharField(max_length=30)
    subject = models.CharField(max_length=200)
    description = models.TextField(default="")
    payload_json = models.JSONField(default=dict)
    status = models.CharField(max_length=30, default="OPEN")
    resolution_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "portal_request"


class PortalRequestEvent(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    request = models.ForeignKey(PortalRequest, on_delete=models.DO_NOTHING, db_column="request_id", related_name="events")
    from_status = models.CharField(max_length=30, null=True, blank=True)
    to_status = models.CharField(max_length=30)
    note = models.TextField(null=True, blank=True)
    actor_type = models.CharField(max_length=10)
    actor_ref = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "portal_request_event"


class PortalRequestSatisfaction(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    request = models.ForeignKey(PortalRequest, on_delete=models.DO_NOTHING, db_column="request_id")
    customer_account = models.ForeignKey(CustomerAccount, on_delete=models.DO_NOTHING, db_column="customer_account_id")
    score = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "portal_request_satisfaction"


class PortalMessage(TenantScopedModel):
    """Mensagem associada a uma cotação, apólice ou pedido (PDF s.15) — nunca
    um chat genérico. `proposer` é a fronteira de acesso do cliente."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    context_type = models.CharField(max_length=10)
    context_ref = models.CharField(max_length=100)
    sender_type = models.CharField(max_length=10)
    sender_ref = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_by_customer_at = models.DateTimeField(null=True, blank=True)
    read_by_staff_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "portal_message"


class PortalNotification(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    customer_account = models.ForeignKey(CustomerAccount, on_delete=models.DO_NOTHING, db_column="customer_account_id")
    dedupe_key = models.CharField(max_length=200)
    code = models.CharField(max_length=60)
    title = models.CharField(max_length=200)
    body = models.TextField(default="")
    link = models.CharField(max_length=300, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "portal_notification"
