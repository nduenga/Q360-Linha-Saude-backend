"""ORM adapters for the self-hosted staff identity schema - replaces the
external Auth0 IdP (DOC-004 s6.1's `JwtActorAdapter`/`JwtActorAuthentication`
are unchanged: they validate a JWT regardless of who issued it, this app
just becomes the issuer). Brand-new schema, not part of ART-005/ART-012
(this table does not exist in any approved Q360 document), same posture as
`apps.customer_portal.infrastructure.models` - `managed = False`, the real
DDL is `infrastructure/migrations/0001_staff_accounts_baseline.py`.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel


class StaffAccount(TenantScopedModel):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    STATUS_CHOICES = [(ACTIVE, "Active"), (DISABLED, "Disabled")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    email = models.EmailField(max_length=320)
    name = models.CharField(max_length=200)
    # django.contrib.auth.hashers output (make_password/check_password) -
    # same primitive apps.customer_portal.infrastructure.otp already uses
    # for OTP hashes, never a bespoke digest.
    password_hash = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "staff_account"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.email} ({self.id})"


class StaffAccountRole(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    staff_account = models.ForeignKey(
        StaffAccount, on_delete=models.DO_NOTHING, db_column="staff_account_id", related_name="role_rows"
    )
    # Validated against domain.permissions.Role by the application layer
    # (StaffAccountRoleService) before insert; also DB-enforced (CHECK
    # constraint in the migration) as defense in depth, same style as
    # ART-012's ck_* constraints elsewhere in this schema.
    role = models.CharField(max_length=30)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "staff_account_role"


class StaffRefreshToken(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    staff_account = models.ForeignKey(
        StaffAccount, on_delete=models.DO_NOTHING, db_column="staff_account_id", related_name="refresh_tokens"
    )
    # Hash only (django.contrib.auth.hashers), never the raw token - same
    # reasoning as otp_hash/password_hash: a DB read/backup leak must not
    # hand out usable credentials.
    token_hash = models.CharField(max_length=200)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "staff_refresh_token"
