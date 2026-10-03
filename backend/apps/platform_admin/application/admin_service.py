"""Gestão dos super administradores da plataforma (equipa interna).

Mais de uma pessoa pode ser super admin; nunca pessoas de uma empresa
cliente (essas são `staff_accounts` de um tenant). A palavra-passe
temporária só existe na resposta que a cria; só o hash é guardado."""
from __future__ import annotations

import secrets
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction

from apps.platform_admin.application.audit_service import record_platform_audit
from apps.platform_admin.domain.errors import PlatformConflictError, PlatformNotFoundError, PlatformRuleError
from apps.platform_admin.infrastructure.models import PlatformAdmin

MIN_PASSWORD = 12


def _temporary_password() -> str:
    return secrets.token_urlsafe(18)


def list_admins() -> list[PlatformAdmin]:
    return list(PlatformAdmin.objects.order_by("created_at"))


def _get(admin_id) -> PlatformAdmin:
    admin = PlatformAdmin.objects.filter(id=admin_id).first()
    if admin is None:
        raise PlatformNotFoundError("Platform administrator not found")
    return admin


@transaction.atomic
def create_admin(*, actor_id: str, email: str, name: str, correlation_id: str | None) -> tuple[PlatformAdmin, str]:
    password = _temporary_password()
    try:
        admin = PlatformAdmin.objects.create(
            id=uuid.uuid4(), email=email.strip().lower(), name=name.strip(), password_hash=make_password(password)
        )
    except IntegrityError as exc:
        raise PlatformConflictError("A platform administrator with this email already exists") from exc
    record_platform_audit(
        actor_id=actor_id, action="platform.admin_created", entity_type="PlatformAdmin", entity_id=str(admin.id),
        correlation_id=correlation_id, metadata={"email": admin.email},
    )
    return admin, password


@transaction.atomic
def set_status(*, actor_id: str, admin_id, status: str, correlation_id: str | None) -> PlatformAdmin:
    admin = _get(admin_id)
    if status == PlatformAdmin.DISABLED:
        if str(admin.id) == actor_id:
            raise PlatformRuleError("You cannot disable your own account")
        others = PlatformAdmin.objects.filter(status=PlatformAdmin.ACTIVE).exclude(id=admin.id).count()
        if admin.status == PlatformAdmin.ACTIVE and others == 0:
            raise PlatformRuleError("At least one active platform administrator is required")
    PlatformAdmin.objects.filter(id=admin.id).update(status=status)
    admin.status = status
    record_platform_audit(
        actor_id=actor_id, action="platform.admin_status_changed", entity_type="PlatformAdmin", entity_id=str(admin.id),
        correlation_id=correlation_id, metadata={"newStatus": status},
    )
    return admin


@transaction.atomic
def reset_password(*, actor_id: str, admin_id, correlation_id: str | None) -> tuple[PlatformAdmin, str]:
    admin = _get(admin_id)
    password = _temporary_password()
    PlatformAdmin.objects.filter(id=admin.id).update(
        password_hash=make_password(password), failed_login_attempts=0, locked_until=None
    )
    record_platform_audit(
        actor_id=actor_id, action="platform.admin_password_reset", entity_type="PlatformAdmin", entity_id=str(admin.id),
        correlation_id=correlation_id,
    )
    return admin, password


def change_own_password(*, admin_id: str, current: str, new: str, correlation_id: str | None) -> None:
    admin = _get(admin_id)
    if not check_password(current, admin.password_hash):
        raise PlatformRuleError("Current password is incorrect")
    if len(new) < MIN_PASSWORD:
        raise PlatformRuleError(f"Password must contain at least {MIN_PASSWORD} characters")
    PlatformAdmin.objects.filter(id=admin.id).update(password_hash=make_password(new))
    record_platform_audit(
        actor_id=str(admin.id), action="platform.admin_password_changed", entity_type="PlatformAdmin",
        entity_id=str(admin.id), correlation_id=correlation_id,
    )


get_admin = _get
