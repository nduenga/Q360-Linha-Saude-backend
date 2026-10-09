"""Admin-facing CRUD over staff_account - backs the Administration screen's
account management UI (Q360-Linha-Sa-de-frontend/src/domains/administration).
Every operation here is already reached only through
`apps.staff_accounts.interfaces.permissions.IsAdminRole` (view layer) and
runs tenant-scoped (`CurrentTenantProvider`, bound from the caller's own
validated JWT) - an ADMIN can only ever manage accounts of their own tenant.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.staff_accounts.domain.errors import DuplicateStaffAccountEmailError
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole, StaffRefreshToken

_audit = AuditService(DjangoAuditRepositoryAdapter())


@dataclass(frozen=True, slots=True)
class StaffAccountView:
    id: uuid.UUID
    email: str
    name: str
    status: str
    roles: list[str]
    last_login_at: object


def _view(account: StaffAccount, roles: list[str]) -> StaffAccountView:
    return StaffAccountView(
        id=account.id, email=account.email, name=account.name, status=account.status,
        roles=roles, last_login_at=account.last_login_at,
    )


def _roles_by_account(account_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    roles_by_account: dict[uuid.UUID, list[str]] = {aid: [] for aid in account_ids}
    for row in StaffAccountRole.objects.filter(staff_account_id__in=account_ids):
        roles_by_account[row.staff_account_id].append(row.role)
    return roles_by_account


def list_accounts() -> list[StaffAccountView]:
    accounts = list(StaffAccount.objects.all().order_by("email"))
    roles_by_account = _roles_by_account([a.id for a in accounts])
    return [_view(a, roles_by_account.get(a.id, [])) for a in accounts]


def create_account(*, email: str, name: str, roles: list[str], password: str | None) -> tuple[StaffAccountView, str | None]:
    """`password`: None generates one and returns it in the result (only
    time the plaintext value ever exists) so the admin can hand it to the
    new user out of band; never logged, never stored anywhere but the hash."""
    tenant_id = CurrentTenantProvider.require().value
    generated_password = None
    if password is None:
        generated_password = secrets.token_urlsafe(12)
        password = generated_password

    try:
        with transaction.atomic():
            account = StaffAccount.objects.create(
                id=uuid.uuid4(), tenant_id=tenant_id, email=email, name=name,
                password_hash=make_password(password),
            )
            StaffAccountRole.objects.bulk_create(
                [
                    StaffAccountRole(id=uuid.uuid4(), tenant_id=tenant_id, staff_account_id=account.id, role=role)
                    for role in roles
                ]
            )
    except IntegrityError as exc:
        raise DuplicateStaffAccountEmailError(f"O email '{email}' já existe neste tenant") from exc

    _audit.record(
        action="staff_account.created", entity_type="StaffAccount", entity_id=str(account.id),
        metadata={"roles": roles},
    )
    return _view(account, roles), generated_password


def update_roles(*, account_id: uuid.UUID, roles: list[str]) -> StaffAccountView:
    account = StaffAccount.objects.filter(id=account_id).first()
    if account is None:
        raise NotFound(f"Não existe a conta de utilizador {account_id} neste tenant")

    tenant_id = CurrentTenantProvider.require().value
    with transaction.atomic():
        StaffAccountRole.objects.filter(staff_account_id=account.id).delete()
        StaffAccountRole.objects.bulk_create(
            [
                StaffAccountRole(id=uuid.uuid4(), tenant_id=tenant_id, staff_account_id=account.id, role=role)
                for role in roles
            ]
        )
    _audit.record(
        action="staff_account.roles_updated", entity_type="StaffAccount", entity_id=str(account.id),
        metadata={"roles": roles},
    )
    return _view(account, roles)


def set_status(*, account_id: uuid.UUID, status: str) -> StaffAccountView:
    account = StaffAccount.objects.filter(id=account_id).first()
    if account is None:
        raise NotFound(f"Não existe a conta de utilizador {account_id} neste tenant")

    with transaction.atomic():
        StaffAccount.objects.filter(id=account.id).update(status=status)
        if status == StaffAccount.DISABLED:
            # Revoke every outstanding session immediately - a disabled
            # account's already-issued access token still works until it
            # expires (stateless JWT, short TTL by design), but it can no
            # longer silently refresh past that.
            StaffRefreshToken.objects.filter(staff_account_id=account.id, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )
    _audit.record(
        action="staff_account.status_changed", entity_type="StaffAccount", entity_id=str(account.id),
        metadata={"status": status},
    )
    roles = list(StaffAccountRole.objects.filter(staff_account_id=account.id).values_list("role", flat=True))
    account.status = status
    return _view(account, roles)


def reset_password(*, account_id: uuid.UUID) -> str:
    """Admin-triggered reset: generates a new temporary password, returns
    it once (plaintext) for the admin to hand to the user out of band."""
    account = StaffAccount.objects.filter(id=account_id).first()
    if account is None:
        raise NotFound(f"Não existe a conta de utilizador {account_id} neste tenant")

    new_password = secrets.token_urlsafe(12)
    with transaction.atomic():
        StaffAccount.objects.filter(id=account.id).update(
            password_hash=make_password(new_password), failed_login_attempts=0, locked_until=None
        )
        StaffRefreshToken.objects.filter(staff_account_id=account.id, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
    _audit.record(action="staff_account.password_reset", entity_type="StaffAccount", entity_id=str(account.id))
    return new_password
