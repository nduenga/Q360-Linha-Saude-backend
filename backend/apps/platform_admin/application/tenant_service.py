"""Ciclo de vida dos tenants (empresas clientes), feito pela plataforma.

Criar um tenant cria, numa só transação, o tenant, os seus dados de empresa
e o primeiro ADMIN com palavra-passe temporária (devolvida uma única vez).
O tenant nasce vazio e isolado: produtos, planos, clientes, cotações e
configuração de negócio são só dele (o catálogo de coberturas de mercado é
criado quando o tenant o usa pela primeira vez)."""
from __future__ import annotations

import secrets
import uuid
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application import tenant_status
from apps.foundation.infrastructure.models import Tenant
from apps.platform_admin.application.audit_service import record_platform_audit
from apps.platform_admin.domain.errors import PlatformConflictError, PlatformNotFoundError
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole

PROFILE_FIELDS = ("legalName", "nif", "email", "phone", "address", "country", "notes")


def _temporary_password() -> str:
    return secrets.token_urlsafe(18)


def _clean_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (profile or {}).items() if k in PROFILE_FIELDS and v not in (None, "")}


def _get(tenant_id) -> Tenant:
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        raise PlatformNotFoundError("Tenant não encontrado")
    return tenant


def _create_admin(tenant_id, email: str, name: str) -> tuple[StaffAccount, str]:
    password = _temporary_password()
    admin = StaffAccount.all_tenants.create(
        id=uuid.uuid4(), tenant_id=tenant_id, email=email, name=name, password_hash=make_password(password),
        status=StaffAccount.ACTIVE, row_version=0,
    )
    StaffAccountRole.all_tenants.create(id=uuid.uuid4(), tenant_id=tenant_id, staff_account_id=admin.id, role="ADMIN")
    return admin, password


@transaction.atomic
def create_tenant(*, actor_id, code, name, profile, admin_email, admin_name, correlation_id):
    # O login do staff é só por email: o email é único em toda a plataforma.
    if StaffAccount.all_tenants.filter(email__iexact=admin_email).exists():
        raise PlatformConflictError("O email do administrador já existe na plataforma")
    try:
        with transaction.atomic():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(), code=code, name=name, status="ACTIVE", row_version=0, profile_json=_clean_profile(profile)
            )
            admin, password = _create_admin(tenant.id, admin_email, admin_name)
    except IntegrityError as exc:
        raise PlatformConflictError("O código do tenant ou o email do administrador já existe") from exc
    record_platform_audit(
        actor_id=actor_id, action="platform.tenant_created", entity_type="Tenant", entity_id=str(tenant.id),
        correlation_id=correlation_id,
        metadata={"tenantCode": tenant.code, "tenantName": tenant.name, "adminId": str(admin.id), "adminEmail": admin.email},
    )
    return tenant, admin, password


def list_tenants(*, actor_id, correlation_id, status: str | None = None, search: str | None = None):
    qs = Tenant.objects.all().order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(name__icontains=search) | qs.filter(code__icontains=search)
    tenants = list(qs)
    record_platform_audit(
        actor_id=actor_id, action="platform.tenants_listed", entity_type="Tenant", correlation_id=correlation_id,
        metadata={"count": len(tenants)},
    )
    return tenants


def tenant_detail(*, tenant_id) -> tuple[Tenant, list[StaffAccount], dict[str, int]]:
    tenant = _get(tenant_id)
    accounts = list(StaffAccount.all_tenants.filter(tenant_id=tenant.id).order_by("created_at"))
    roles: dict[Any, list[str]] = {}
    for row in StaffAccountRole.all_tenants.filter(tenant_id=tenant.id):
        roles.setdefault(row.staff_account_id, []).append(row.role)
    for account in accounts:
        account.roles_list = sorted(roles.get(account.id, []))  # type: ignore[attr-defined]
    stats = {
        "staffAccounts": len(accounts),
        "activeStaffAccounts": sum(1 for a in accounts if a.status == StaffAccount.ACTIVE),
    }
    return tenant, accounts, stats


@transaction.atomic
def update_tenant(*, actor_id, tenant_id, name=None, profile=None, status=None, correlation_id=None) -> Tenant:
    tenant = _get(tenant_id)
    changes: dict[str, Any] = {}
    if name is not None:
        tenant.name = name.strip()
        changes["name"] = tenant.name
    if profile is not None:
        tenant.profile_json = {**(tenant.profile_json or {}), **_clean_profile(profile)}
        changes["profile"] = sorted(_clean_profile(profile))
    old_status = tenant.status
    if status is not None and status != old_status:
        tenant.status = status
        changes["oldStatus"], changes["newStatus"] = old_status, status
    Tenant.objects.filter(id=tenant.id).update(
        name=tenant.name, profile_json=tenant.profile_json, status=tenant.status,
        updated_at=timezone.now(), row_version=tenant.row_version + 1,
    )
    tenant.row_version += 1
    tenant_status.invalidate(tenant.id)
    action = "platform.tenant_status_changed" if "newStatus" in changes else "platform.tenant_updated"
    record_platform_audit(
        actor_id=actor_id, action=action, entity_type="Tenant", entity_id=str(tenant.id),
        correlation_id=correlation_id, metadata=changes,
    )
    return tenant


@transaction.atomic
def add_tenant_admin(*, actor_id, tenant_id, email, name, correlation_id):
    tenant = _get(tenant_id)
    if StaffAccount.all_tenants.filter(email__iexact=email).exists():
        raise PlatformConflictError("O email já existe na plataforma")
    admin, password = _create_admin(tenant.id, email, name)
    record_platform_audit(
        actor_id=actor_id, action="platform.tenant_admin_added", entity_type="Tenant", entity_id=str(tenant.id),
        correlation_id=correlation_id, metadata={"adminId": str(admin.id), "adminEmail": admin.email},
    )
    return admin, password


@transaction.atomic
def reset_tenant_account_password(*, actor_id, tenant_id, account_id, correlation_id):
    tenant = _get(tenant_id)
    account = StaffAccount.all_tenants.filter(id=account_id, tenant_id=tenant.id).first()
    if account is None:
        raise PlatformNotFoundError("Conta não encontrada neste tenant")
    password = _temporary_password()
    StaffAccount.all_tenants.filter(id=account.id).update(
        password_hash=make_password(password), failed_login_attempts=0, locked_until=None
    )
    record_platform_audit(
        actor_id=actor_id, action="platform.tenant_account_password_reset", entity_type="StaffAccount",
        entity_id=str(account.id), correlation_id=correlation_id, metadata={"tenantId": str(tenant.id)},
    )
    return account, password
