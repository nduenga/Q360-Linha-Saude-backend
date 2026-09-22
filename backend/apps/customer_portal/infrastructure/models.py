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
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "customer_login_challenge"
