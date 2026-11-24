"""Recuperação e mudança de palavra-passe do staff (e dos super administradores).

Recuperação: o token é assinado (`django.core.signing`) e leva uma impressão
da palavra-passe atual. Por isso é de uso único sem tabela nenhuma: assim que
a palavra-passe muda (pela ligação, por reposição de um administrador ou pelo
próprio utilizador) a impressão deixa de bater e o token morre. A resposta ao
pedido é sempre a mesma exista ou não o email (nunca confirma contas)."""
from __future__ import annotations

import hashlib
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.customer_portal.domain.password import validate_password_strength
from apps.foundation.domain.permissions import scopes_for_roles, Role
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.models import Tenant
from apps.platform_admin.application.admin_service import MIN_PASSWORD as PLATFORM_MIN_PASSWORD
from apps.platform_admin.application.audit_service import record_platform_audit
from apps.platform_admin.infrastructure.models import PlatformAdmin
from apps.staff_accounts.application import credential_mail
from apps.staff_accounts.application.auth_service import AuthResult, _generate_refresh_token
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole, StaffRefreshToken
from apps.staff_accounts.infrastructure.staff_token import issue_access_token

_SALT = "q360.staff.password-recovery"
_STAFF, _PLATFORM = "S", "P"


class InvalidRecoveryTokenError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class WrongCurrentPasswordError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:24]


def _make_token(kind: str, account) -> str:
    return signing.dumps({"k": kind, "i": str(account.id), "f": _fingerprint(account.password_hash)}, salt=_SALT)


def request_recovery(*, email: str, correlation_id: str | None) -> None:
    """Envia a ligação de recuperação se o email for de uma conta ativa; não devolve nada."""
    email = email.strip()
    ttl = settings.Q360_STAFF_RECOVERY_TTL_MINUTES
    account = StaffAccount.all_tenants.filter(email__iexact=email).first()
    if account is not None:
        tenant = Tenant.objects.filter(id=account.tenant_id).first()
        if account.status != StaffAccount.ACTIVE or tenant is None or tenant.status != "ACTIVE":
            return
        with transaction.atomic():
            credential_mail.send_recovery_email(
                to_email=account.email, name=account.name, token=_make_token(_STAFF, account), tenant_name=tenant.name,
                account_id=str(account.id), ttl_minutes=ttl, tenant_id=tenant.id,
            )
            record_platform_audit(actor_id=str(account.id), action="platform.password_recovery_requested",
                                  entity_type="StaffAccount", entity_id=str(account.id), correlation_id=correlation_id,
                                  tenant_id=tenant.id)
        return
    admin = PlatformAdmin.objects.filter(email__iexact=email, status=PlatformAdmin.ACTIVE).first()
    if admin is not None:
        with transaction.atomic():
            credential_mail.send_recovery_email(
                to_email=admin.email, name=admin.name, token=_make_token(_PLATFORM, admin), tenant_name=None,
                account_id=str(admin.id), ttl_minutes=ttl, entity="PlatformAdmin",
            )
            record_platform_audit(actor_id=str(admin.id), action="platform.password_recovery_requested",
                                  entity_type="PlatformAdmin", entity_id=str(admin.id), correlation_id=correlation_id)


def _load(token: str):
    try:
        data = signing.loads(token, salt=_SALT, max_age=settings.Q360_STAFF_RECOVERY_TTL_MINUTES * 60)
        kind, account_id, fingerprint = data["k"], uuid.UUID(data["i"]), data["f"]
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        raise InvalidRecoveryTokenError("A ligação é inválida ou expirou. Peça uma nova.") from None
    model = StaffAccount.all_tenants if kind == _STAFF else PlatformAdmin.objects if kind == _PLATFORM else None
    account = model.filter(id=account_id, status="ACTIVE").first() if model is not None else None
    if account is None or _fingerprint(account.password_hash) != fingerprint:
        raise InvalidRecoveryTokenError("A ligação é inválida ou expirou. Peça uma nova.")
    return kind, account


def reset_with_token(*, token: str, new_password: str, correlation_id: str | None) -> None:
    kind, account = _load(token)
    if kind == _PLATFORM:
        if len(new_password) < PLATFORM_MIN_PASSWORD:
            raise WrongCurrentPasswordError(f"A palavra-passe tem de ter pelo menos {PLATFORM_MIN_PASSWORD} caracteres")
        validate_password_strength(new_password, email=account.email)
        PlatformAdmin.objects.filter(id=account.id).update(
            password_hash=make_password(new_password), failed_login_attempts=0, locked_until=None
        )
        record_platform_audit(actor_id=str(account.id), action="platform.password_recovered",
                              entity_type="PlatformAdmin", entity_id=str(account.id), correlation_id=correlation_id)
        return
    validate_password_strength(new_password, email=account.email)
    with transaction.atomic():
        StaffAccount.all_tenants.filter(id=account.id).update(
            password_hash=make_password(new_password), failed_login_attempts=0, locked_until=None
        )
        StaffRefreshToken.all_tenants.filter(staff_account_id=account.id, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        record_platform_audit(actor_id=str(account.id), action="platform.password_recovered",
                              entity_type="StaffAccount", entity_id=str(account.id), correlation_id=correlation_id,
                              tenant_id=account.tenant_id)


def change_own_password(*, account_id: str, current: str, new: str, correlation_id: str | None) -> AuthResult:
    """O utilizador autenticado muda a sua palavra-passe (p.ex. a temporária).

    Termina as outras sessões (refresh tokens) e devolve uma sessão nova, para
    quem muda não ser desligado a seguir."""
    account = StaffAccount.objects.filter(id=account_id).first()
    if account is None or not check_password(current, account.password_hash):
        raise WrongCurrentPasswordError("A palavra-passe atual está incorreta")
    if new == current:
        raise WrongCurrentPasswordError("A nova palavra-passe tem de ser diferente da atual")
    validate_password_strength(new, email=account.email)
    with transaction.atomic():
        StaffAccount.objects.filter(id=account.id).update(password_hash=make_password(new))
        StaffRefreshToken.objects.filter(staff_account_id=account.id, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        refresh_token, _ = _generate_refresh_token(tenant_id=account.tenant_id, staff_account_id=account.id)
        record_platform_audit(actor_id=str(account.id), action="platform.password_changed",
                              entity_type="StaffAccount", entity_id=str(account.id), correlation_id=correlation_id,
                              tenant_id=account.tenant_id)
    roles = list(StaffAccountRole.objects.filter(staff_account_id=account.id).values_list("role", flat=True))
    scopes = scopes_for_roles(frozenset(Role(r) for r in roles), tenant_id=account.tenant_id)
    access_token, expires_in = issue_access_token(
        actor_id=account.id, tenant_id=account.tenant_id, roles=roles, scopes=[s.value for s in scopes]
    )
    return AuthResult(access_token=access_token, expires_in=expires_in, refresh_token=refresh_token,
                      account=account, roles=roles)
