"""StaffAccountAuthService - self-hosted replacement for the Auth0 login
step. Everything downstream (JwtActorAuthentication, require_scope,
require_permission, ROLE_PERMISSIONS) is completely unchanged; this service
only has to produce a token shaped the way JwtActorAdapter already expects
(see infrastructure/staff_token.py).
"""
from __future__ import annotations

import datetime
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.customer_portal.domain.lockout import LockoutState, is_locked, register_failure, register_success
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role, scopes_for_roles
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.foundation.infrastructure.models import Tenant
from apps.staff_accounts.domain.errors import (
    InvalidRefreshTokenError,
    InvalidStaffCredentialsError,
    StaffAccountLockedError,
)
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole, StaffRefreshToken
from apps.staff_accounts.infrastructure.staff_token import issue_access_token

_audit = AuditService(DjangoAuditRepositoryAdapter())
_REFRESH_TOKEN_SECRET_BYTES = 32


def _bind_actor_for(tenant_id: uuid.UUID, actor_id: str) -> None:
    """Enough of an Actor to make TenantScopedManager/AuditService work for
    the rest of this request - mirrors
    apps.customer_portal.interfaces.views._bind_anonymous_customer_actor.
    Real roles/scopes are only known once the account row is found."""
    CurrentActorProvider.bind(
        Actor(actor_id=actor_id, tenant_id=TenantId.parse(tenant_id), roles=frozenset(), scopes=frozenset())
    )


def _generate_refresh_token(*, tenant_id: uuid.UUID, staff_account_id: uuid.UUID) -> tuple[str, StaffRefreshToken]:
    secret = secrets.token_urlsafe(_REFRESH_TOKEN_SECRET_BYTES)
    row = StaffRefreshToken.objects.create(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        staff_account_id=staff_account_id,
        token_hash=make_password(secret),
        expires_at=timezone.now() + datetime.timedelta(seconds=settings.Q360_STAFF_REFRESH_TOKEN_TTL_SECONDS),
    )
    # Opaque `<row id>.<secret>` - the id makes lookup an indexed equality
    # check instead of scanning every issued token to find which hash
    # matches (same idea as an API key's public prefix).
    return f"{row.id}.{secret}", row


class AuthResult:
    def __init__(self, *, access_token: str, expires_in: int, refresh_token: str, account: StaffAccount, roles: list[str]):
        self.access_token = access_token
        self.expires_in = expires_in
        self.refresh_token = refresh_token
        self.account = account
        self.roles = roles


class StaffAccountAuthService:
    def login(self, *, email: str, password: str, correlation_id: str | None) -> AuthResult:
        # No tenant is known yet (login is by email alone, no tenant
        # selector in the UI) - this is exactly the "system/admin job that
        # must legitimately cross tenants" the `all_tenants` escape hatch
        # on TenantScopedModel exists for (apps.foundation.infrastructure.
        # tenant_scoping), not a business-data query.
        account = StaffAccount.all_tenants.filter(email__iexact=email).first()
        if account is None or account.status != StaffAccount.ACTIVE:
            raise InvalidStaffCredentialsError("Invalid email or password")

        tenant = Tenant.objects.filter(id=account.tenant_id).first()
        if tenant is None or tenant.status != "ACTIVE":
            raise InvalidStaffCredentialsError("Tenant is suspended or inactive")

        _bind_actor_for(account.tenant_id, str(account.id))

        now = timezone.now()
        state = LockoutState(failed_attempts=account.failed_login_attempts, locked_until=account.locked_until)
        if is_locked(state, now=now):
            raise StaffAccountLockedError("Account temporarily locked after repeated failed attempts")

        if not check_password(password, account.password_hash):
            self._register_failure(account, state, now, correlation_id)
            raise InvalidStaffCredentialsError("Invalid email or password")

        roles = list(
            StaffAccountRole.objects.filter(staff_account_id=account.id).values_list("role", flat=True)
        )
        scopes = scopes_for_roles(frozenset(Role(r) for r in roles), tenant_id=account.tenant_id)

        access_token, expires_in = issue_access_token(
            actor_id=account.id, tenant_id=account.tenant_id, roles=roles, scopes=[s.value for s in scopes]
        )
        refresh_token, _ = _generate_refresh_token(tenant_id=account.tenant_id, staff_account_id=account.id)

        StaffAccount.objects.filter(id=account.id).update(
            failed_login_attempts=0, locked_until=None, last_login_at=now
        )
        _audit.record(
            action="staff_account.login_succeeded",
            entity_type="StaffAccount",
            entity_id=str(account.id),
            correlation_id=correlation_id,
        )
        return AuthResult(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            account=account,
            roles=roles,
        )

    def _register_failure(self, account: StaffAccount, state: LockoutState, now, correlation_id: str | None) -> None:
        new_state = register_failure(
            state,
            now=now,
            max_attempts=settings.Q360_STAFF_MAX_FAILED_ATTEMPTS,
            lockout_minutes=settings.Q360_STAFF_LOCKOUT_MINUTES,
        )
        StaffAccount.objects.filter(id=account.id).update(
            failed_login_attempts=new_state.failed_attempts, locked_until=new_state.locked_until
        )
        _audit.record(
            action="staff_account.login_failed",
            entity_type="StaffAccount",
            entity_id=str(account.id),
            correlation_id=correlation_id,
            metadata={"locked": new_state.locked_until is not None},
        )

    def refresh(self, *, refresh_token: str, correlation_id: str | None) -> AuthResult:
        token_id, _, secret = refresh_token.partition(".")
        if not token_id or not secret:
            raise InvalidRefreshTokenError("Malformed refresh token")

        row = StaffRefreshToken.all_tenants.filter(id=token_id).first()
        if row is None or row.revoked_at is not None or row.expires_at <= timezone.now():
            raise InvalidRefreshTokenError("Refresh token is invalid, expired, or already used")
        if not check_password(secret, row.token_hash):
            raise InvalidRefreshTokenError("Refresh token is invalid, expired, or already used")

        tenant = Tenant.objects.filter(id=row.tenant_id).first()
        if tenant is None or tenant.status != "ACTIVE":
            raise InvalidRefreshTokenError("Tenant is suspended or inactive")

        _bind_actor_for(row.tenant_id, str(row.staff_account_id))
        account = StaffAccount.objects.filter(id=row.staff_account_id).first()
        if account is None or account.status != StaffAccount.ACTIVE:
            raise InvalidRefreshTokenError("Account is no longer active")

        roles = list(
            StaffAccountRole.objects.filter(staff_account_id=account.id).values_list("role", flat=True)
        )
        scopes = scopes_for_roles(frozenset(Role(r) for r in roles), tenant_id=account.tenant_id)
        access_token, expires_in = issue_access_token(
            actor_id=account.id, tenant_id=account.tenant_id, roles=roles, scopes=[s.value for s in scopes]
        )

        with transaction.atomic():
            # Rotation: the old refresh token is single-use - a second use
            # of the same raw value (e.g. a stolen/replayed one) fails the
            # `revoked_at is not None` check above on its next attempt.
            StaffRefreshToken.objects.filter(id=row.id).update(revoked_at=timezone.now())
            new_refresh_token, _ = _generate_refresh_token(tenant_id=account.tenant_id, staff_account_id=account.id)

        return AuthResult(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=new_refresh_token,
            account=account,
            roles=roles,
        )

    def logout(self, *, refresh_token: str) -> None:
        token_id, _, _secret = refresh_token.partition(".")
        if not token_id:
            return
        # Always succeeds regardless of whether the token was valid -
        # logging out with a stale/foreign token must not error.
        StaffRefreshToken.all_tenants.filter(id=token_id).update(revoked_at=timezone.now())
