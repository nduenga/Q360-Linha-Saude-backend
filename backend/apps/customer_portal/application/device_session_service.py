"""Sessões por dispositivo do Portal Cliente para a app móvel
(roadmap_mobile.md, Fase 1 — pontos 3 e 6).

O token de acesso continua curto e igual ao da web (`PortalTokenService`); o
telemóvel recebe também um token de renovação:

  - só o hash SHA-256 fica na base de dados (o token tem 256 bits aleatórios,
    por isso não precisa de um hash lento);
  - formato `<id da sessão>.<segredo>`: a sessão encontra-se por chave primária;
  - roda a cada uso e dura `CUSTOMER_PORTAL_REFRESH_TTL_DAYS` desde o último uso;
  - apresentar o token anterior à última rotação é reutilização (alguém copiou
    o token): a sessão é terminada, nos dois lados;
  - morre quando a palavra-passe muda ou o cliente termina a sessão.

Quem não envia dispositivo (a web) não passa por aqui: continua a receber só o
token de acesso, como antes.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.customer_portal.domain.errors import InvalidPortalCredentialsError, PortalAccountLockedError
from apps.customer_portal.domain.lockout import LockoutState, is_locked
from apps.customer_portal.infrastructure.models import (
    CustomerAccount,
    CustomerAccountProposer,
    CustomerDeviceSession,
    CustomerPushDevice,
)
from apps.customer_portal.infrastructure.portal_token import PortalTokenService
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter

_audit = AuditService(DjangoAuditRepositoryAdapter())
_tokens = PortalTokenService()

INVALID_SESSION = "Sessão inválida ou expirada: inicie sessão de novo"


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    device_name: str = ""
    platform: str = "OTHER"
    app_version: str = ""


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _tenant_id() -> uuid.UUID:
    return CurrentTenantProvider.require().value


def _refresh_ttl() -> datetime.timedelta:
    return datetime.timedelta(days=settings.CUSTOMER_PORTAL_REFRESH_TTL_DAYS)


def _proposer_ids(account: CustomerAccount) -> list[uuid.UUID]:
    return list(CustomerAccountProposer.objects.filter(customer_account=account).values_list("proposer_id", flat=True))


def _parse(refresh_token: str) -> tuple[uuid.UUID, str] | None:
    session_part, _, secret = (refresh_token or "").partition(".")
    if not secret:
        return None
    try:
        return uuid.UUID(session_part), secret
    except ValueError:
        return None


def _compose(session_id: uuid.UUID, secret: str) -> str:
    return f"{session_id}.{secret}"


def _device_metadata(device: DeviceInfo | None) -> dict:
    if device is None:
        return {}
    return {"deviceId": device.device_id, "platform": device.platform, "appVersion": device.app_version}


def deactivate_push_devices(session_ids: list[uuid.UUID]) -> None:
    """Terminada a sessão, o telemóvel deixa de receber notificações dessa conta."""
    if session_ids:
        CustomerPushDevice.objects.filter(device_session_id__in=session_ids, active=True).update(active=False)


# ------------------------------------------------------------------ abrir
def open_session(account: CustomerAccount, device: DeviceInfo | None) -> SessionTokens:
    """Token de acesso para a conta; com `device` (app móvel) cria também a
    sessão do dispositivo e o token de renovação."""
    proposer_ids = _proposer_ids(account)
    if device is None:
        token, ttl = _tokens.issue(
            tenant_id=_tenant_id(), customer_account_id=account.id, proposer_ids=proposer_ids
        )
        return SessionTokens(access_token=token, expires_in=ttl)

    now = timezone.now()
    secret = secrets.token_urlsafe(32)
    with transaction.atomic():
        # Um dispositivo tem uma sessão: entrar de novo substitui a anterior.
        previous = list(
            CustomerDeviceSession.objects.filter(
                customer_account=account, device_id=device.device_id, revoked_at__isnull=True
            ).values_list("id", flat=True)
        )
        if previous:
            CustomerDeviceSession.objects.filter(id__in=previous).update(revoked_at=now, revoked_reason="REPLACED")
        session = CustomerDeviceSession.objects.create(
            tenant_id=_tenant_id(), customer_account=account, device_id=device.device_id,
            device_name=device.device_name, platform=device.platform, app_version=device.app_version,
            token_hash=_hash(secret), expires_at=now + _refresh_ttl(),
        )
    token, ttl = _tokens.issue(
        tenant_id=_tenant_id(), customer_account_id=account.id, proposer_ids=proposer_ids, session_id=session.id
    )
    return SessionTokens(
        access_token=token, expires_in=ttl, refresh_token=_compose(session.id, secret),
        refresh_expires_in=int(_refresh_ttl().total_seconds()),
    )


# --------------------------------------------------------------- renovar
def refresh(refresh_token: str, *, app_version: str = "", correlation_id: str | None = None) -> SessionTokens:
    parsed = _parse(refresh_token)
    if parsed is None:
        raise InvalidPortalCredentialsError(INVALID_SESSION)
    session_id, secret = parsed
    presented = _hash(secret)
    now = timezone.now()
    reused = False
    result: SessionTokens | None = None

    with transaction.atomic():
        session = CustomerDeviceSession.objects.select_for_update().filter(id=session_id).first()
        if session is None or session.revoked_at is not None:
            raise InvalidPortalCredentialsError(INVALID_SESSION)
        if hmac.compare_digest(presented, session.token_hash):
            if session.expires_at <= now:
                CustomerDeviceSession.objects.filter(id=session.id).update(revoked_at=now, revoked_reason="EXPIRED")
                deactivate_push_devices([session.id])
            else:
                account = CustomerAccount.objects.filter(id=session.customer_account_id).first()
                if account is None or not account.password_hash:
                    raise InvalidPortalCredentialsError(INVALID_SESSION)
                if is_locked(
                    LockoutState(failed_attempts=account.failed_otp_attempts, locked_until=account.locked_until), now=now
                ):
                    raise PortalAccountLockedError("Conta temporariamente bloqueada após tentativas falhadas repetidas")
                new_secret = secrets.token_urlsafe(32)
                changes = {
                    "token_hash": _hash(new_secret), "previous_token_hash": session.token_hash,
                    "last_used_at": now, "expires_at": now + _refresh_ttl(),
                }
                if app_version:
                    changes["app_version"] = app_version
                CustomerDeviceSession.objects.filter(id=session.id).update(**changes)
                access, ttl = _tokens.issue(
                    tenant_id=_tenant_id(), customer_account_id=account.id, proposer_ids=_proposer_ids(account),
                    session_id=session.id,
                )
                result = SessionTokens(
                    access_token=access, expires_in=ttl, refresh_token=_compose(session.id, new_secret),
                    refresh_expires_in=int(_refresh_ttl().total_seconds()),
                )
        elif session.previous_token_hash and hmac.compare_digest(presented, session.previous_token_hash):
            reused = True
            CustomerDeviceSession.objects.filter(id=session.id).update(revoked_at=now, revoked_reason="REUSE_DETECTED")
            deactivate_push_devices([session.id])

    if reused:
        # Fora da transação: a revogação tem de ficar gravada mesmo com o erro.
        _audit.record(
            action="customer_portal.refresh_token_reused", entity_type="CustomerDeviceSession",
            entity_id=str(session_id), correlation_id=correlation_id,
        )
    if result is None:
        raise InvalidPortalCredentialsError(INVALID_SESSION)
    return result


# ---------------------------------------------------------------- revogar
def revoke_by_refresh_token(refresh_token: str) -> None:
    """Terminar sessão a partir do telemóvel (o token de acesso pode já ter
    expirado). Idempotente e silencioso: nunca diz se o token era válido."""
    parsed = _parse(refresh_token)
    if parsed is None:
        return
    session_id, secret = parsed
    session = CustomerDeviceSession.objects.filter(id=session_id, revoked_at__isnull=True).first()
    if session is None:
        return
    known = [session.token_hash] + ([session.previous_token_hash] if session.previous_token_hash else [])
    if not any(hmac.compare_digest(_hash(secret), h) for h in known):
        return
    _revoke([session.id], reason="LOGOUT")


def revoke_session(account_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    """«Dispositivos ligados»: o cliente termina uma das suas sessões."""
    owned = CustomerDeviceSession.objects.filter(
        id=session_id, customer_account_id=account_id, revoked_at__isnull=True
    ).values_list("id", flat=True)
    ids = list(owned)
    if not ids:
        return False
    _revoke(ids, reason="USER")
    return True


def revoke_all(account_id: uuid.UUID, *, reason: str) -> int:
    ids = list(
        CustomerDeviceSession.objects.filter(customer_account_id=account_id, revoked_at__isnull=True)
        .values_list("id", flat=True)
    )
    if ids:
        _revoke(ids, reason=reason)
    return len(ids)


def _revoke(session_ids: list[uuid.UUID], *, reason: str) -> None:
    with transaction.atomic():
        CustomerDeviceSession.objects.filter(id__in=session_ids, revoked_at__isnull=True).update(
            revoked_at=timezone.now(), revoked_reason=reason
        )
        deactivate_push_devices(session_ids)


def is_active(session_id: uuid.UUID, account_id: uuid.UUID) -> bool:
    """Usado pela autenticação: um token de acesso com `sid` só vale enquanto
    a sessão não for terminada (o tenant ainda não está ligado nessa altura)."""
    return CustomerDeviceSession.all_tenants.filter(
        id=session_id, customer_account_id=account_id, revoked_at__isnull=True
    ).exists()


# ----------------------------------------------------------------- listar
def list_sessions(account_id: uuid.UUID, *, current_session_id: uuid.UUID | None) -> list[dict]:
    now = timezone.now()
    rows = CustomerDeviceSession.objects.filter(
        customer_account_id=account_id, revoked_at__isnull=True, expires_at__gt=now
    ).order_by("-last_used_at")
    return [
        {
            "id": str(row.id), "deviceName": row.device_name or "Dispositivo", "platform": row.platform,
            "appVersion": row.app_version, "createdAt": row.created_at, "lastUsedAt": row.last_used_at,
            "current": current_session_id is not None and row.id == current_session_id,
        }
        for row in rows
    ]
