"""Servidor SMTP configurado no painel (plataforma e, opcionalmente, por seguradora).

Quem envia (`resolve`):
1. a configuração da seguradora, se estiver ativa **e** o último teste correu bem;
2. senão a da plataforma, com as mesmas condições;
3. senão as variáveis de ambiente (`EMAIL_*`), como sempre foi.

A palavra-passe SMTP guarda-se cifrada (Fernet) e nunca sai pela API. Como uma
seguradora escolhe o servidor, o destino é validado (portas de email e, fora de
desenvolvimento, nada de endereços internos) para o teste de ligação não servir
para explorar a rede interna."""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import logging
import socket
import uuid
from dataclasses import dataclass
from email.utils import formataddr, parseaddr
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.foundation.domain.problem import DomainProblem
from apps.platform_admin.application.audit_service import record_platform_audit
from apps.platform_admin.infrastructure.models import EmailSettings

logger = logging.getLogger(__name__)

SECURITIES = ("STARTTLS", "SSL", "NONE")
ALLOWED_PORTS = (25, 465, 587, 2525)
_CACHE_SECONDS = 30
_NOT_SET = object()


class EmailSettingsError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


# ------------------------------------------------------------------ segredos
def _fernet():
    from cryptography.fernet import Fernet

    key = settings.Q360_SECRETS_KEY or settings.SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        logger.error("Não foi possível decifrar a palavra-passe SMTP (a chave Q360_SECRETS_KEY mudou?).")
        return ""


# ---------------------------------------------------------------- validação
def _clean_address(value: str, label: str, *, required: bool) -> str:
    value = (value or "").strip()
    if not value:
        if required:
            raise EmailSettingsError(f"{label} é obrigatório.")
        return ""
    try:
        validate_email(parseaddr(value)[1] or value)
    except ValidationError:
        raise EmailSettingsError(f"{label} não é um endereço de email válido.") from None
    return value


def _check_destination(host: str, port: int) -> None:
    if port not in ALLOWED_PORTS:
        raise EmailSettingsError(f"A porta {port} não é permitida. Use uma de: {', '.join(map(str, ALLOWED_PORTS))}.")
    if settings.DEBUG or settings.Q360_EMAIL_CONFIG_BACKEND.endswith("locmem.EmailBackend"):
        return
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except OSError:
        raise EmailSettingsError(f"Não foi possível resolver o servidor «{host}».") from None
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise EmailSettingsError("O servidor indicado aponta para uma rede interna e não é permitido.")


def validate_payload(data: dict[str, Any], *, existing: EmailSettings | None) -> dict[str, Any]:
    host = (data.get("host") if "host" in data else getattr(existing, "host", "") or "").strip().lower()
    if not host or len(host) > 255 or any(c in host for c in " /\\@"):
        raise EmailSettingsError("Indique um servidor (host) válido, p.ex. smtp.o-seu-fornecedor.com.")
    port = int(data.get("port", getattr(existing, "port", 587)))
    security = data.get("security", getattr(existing, "security", "STARTTLS"))
    if security not in SECURITIES:
        raise EmailSettingsError("A segurança tem de ser STARTTLS, SSL ou NONE.")
    timeout = int(data.get("timeoutSeconds", getattr(existing, "timeout_seconds", 20)))
    if not 3 <= timeout <= 60:
        raise EmailSettingsError("O tempo limite tem de estar entre 3 e 60 segundos.")
    _check_destination(host, port)
    out = {
        "host": host, "port": port, "security": security, "timeout_seconds": timeout,
        "username": (data["username"] if "username" in data else getattr(existing, "username", "")).strip(),
        "from_address": _clean_address(data["fromAddress"] if "fromAddress" in data
                                       else getattr(existing, "from_address", ""), "O remetente", required=True),
        "from_name": (data["fromName"] if "fromName" in data else getattr(existing, "from_name", "")).strip(),
        "reply_to": _clean_address(data["replyTo"] if "replyTo" in data else getattr(existing, "reply_to", ""),
                                   "O endereço de resposta", required=False),
        "enabled": bool(data.get("enabled", getattr(existing, "enabled", True))),
    }
    return out


# ------------------------------------------------------------------ ligação
def _connection(row: EmailSettings, *, fail_silently: bool = False):
    # Utilizador e palavra-passe vazios têm de seguir como "" e não None: com None o
    # Django usa EMAIL_HOST_USER/EMAIL_HOST_PASSWORD do .env e o servidor configurado
    # no painel acabava a enviar com a conta do ambiente.
    return get_connection(
        backend=settings.Q360_EMAIL_CONFIG_BACKEND, host=row.host, port=row.port, username=row.username or "",
        password=decrypt_secret(row.password_enc) or "", use_tls=row.security == "STARTTLS",
        use_ssl=row.security == "SSL", timeout=row.timeout_seconds, fail_silently=fail_silently,
    )


def check_connection(row: EmailSettings) -> tuple[bool, str]:
    """Abre sessão e autentica no servidor, sem enviar nada."""
    try:
        connection = _connection(row)
        connection.open()
        try:
            smtp = getattr(connection, "connection", None)
            if smtp is not None and not row.username and smtp.has_extn("auth"):
                return False, "O servidor exige autenticação: indique o utilizador e a palavra-passe."
        finally:
            connection.close()
    except Exception as exc:  # noqa: BLE001 - qualquer falha SMTP é o resultado do teste
        return False, f"{type(exc).__name__}: {exc}"[:500]
    return True, ""


def _record_test(row: EmailSettings, ok: bool, error: str) -> None:
    EmailSettings.objects.filter(id=row.id).update(last_test_at=timezone.now(), last_test_ok=ok, last_test_error=error)
    row.last_test_at, row.last_test_ok, row.last_test_error = timezone.now(), ok, error


# ---------------------------------------------------------------- resolução
@dataclass(frozen=True, slots=True)
class Resolved:
    source: str  # TENANT | PLATFORM | ENV
    connection: Any
    from_address: str | None
    from_name: str | None
    reply_to: str | None


def _cache_key(tenant_id) -> str:
    return f"q360:email-settings:{tenant_id or 'platform'}"


def invalidate(tenant_id=None) -> None:
    cache.delete(_cache_key(tenant_id))
    cache.delete(_cache_key(None))


def _usable(tenant_id) -> EmailSettings | None:
    row = EmailSettings.objects.filter(tenant_id=tenant_id).first()
    return row if row is not None and row.enabled and row.last_test_ok else None


def _row_for(tenant_id) -> tuple[str, EmailSettings | None]:
    key = _cache_key(tenant_id)
    hit = cache.get(key)
    if hit is None:
        row, source = None, "ENV"
        if tenant_id is not None and (row := _usable(tenant_id)) is not None:
            source = "TENANT"
        elif (row := _usable(None)) is not None:
            source = "PLATFORM"
        hit = (source, row)
        cache.set(key, hit, _CACHE_SECONDS)
    return hit


def resolve(tenant_id=None) -> Resolved:
    """Servidor e remetente a usar para esta seguradora (None: só plataforma)."""
    source, row = _row_for(tenant_id)
    if row is None:
        return Resolved("ENV", None, None, None, None)
    return Resolved(source, _connection(row), row.from_address, row.from_name or None, row.reply_to or None)


def apply_sender(from_email: str, resolved: Resolved) -> str:
    """Troca o endereço do remetente pelo configurado, mantendo o nome que o chamador montou."""
    if not resolved.from_address:
        return from_email
    name = parseaddr(from_email)[0] or resolved.from_name or ""
    return formataddr((name, resolved.from_address)) if name else resolved.from_address


def effective_source(tenant_id=None) -> str:
    return _row_for(tenant_id)[0]


# ---------------------------------------------------------------------- API
def _tenant_key(tenant_id):
    return uuid.UUID(str(tenant_id)) if tenant_id is not None else None


def get_row(tenant_id=None) -> EmailSettings | None:
    return EmailSettings.objects.filter(tenant_id=_tenant_key(tenant_id)).first()


def to_dict(row: EmailSettings | None, *, tenant_id=None) -> dict[str, Any]:
    """Representação pública: nunca inclui a palavra-passe, só se existe."""
    source = effective_source(tenant_id)
    inherited = None
    if row is None:
        inherited = source if source != "TENANT" else None
        if inherited == "ENV" and not _env_is_configured():
            inherited = None
    base = {"configured": row is not None, "scope": "TENANT" if tenant_id is not None else "PLATFORM",
            "effectiveSource": source, "inheritedFrom": inherited}
    if row is None:
        return {**base, "host": None, "port": 587, "security": "STARTTLS", "username": "", "hasPassword": False,
                "fromAddress": "", "fromName": "", "replyTo": "", "timeoutSeconds": 20, "enabled": False,
                "lastTest": None, "updatedAt": None}
    return {
        **base, "host": row.host, "port": row.port, "security": row.security, "username": row.username,
        "hasPassword": bool(row.password_enc), "fromAddress": row.from_address, "fromName": row.from_name,
        "replyTo": row.reply_to, "timeoutSeconds": row.timeout_seconds, "enabled": row.enabled,
        "lastTest": ({"at": row.last_test_at, "ok": row.last_test_ok, "error": row.last_test_error or None}
                     if row.last_test_at else None),
        "updatedAt": row.updated_at,
    }


def _env_is_configured() -> bool:
    return "smtp" in settings.EMAIL_BACKEND and bool(settings.EMAIL_HOST)


def save(*, tenant_id=None, data: dict[str, Any], actor_id: str, correlation_id: str | None = None) -> EmailSettings:
    """Grava a configuração e testa logo a ligação. `password` omitida mantém a
    atual; `""` apaga-a. Só fica em uso se o teste correr bem e estiver ativa."""
    tenant_id = _tenant_key(tenant_id)
    existing = get_row(tenant_id)
    clean = validate_payload(data, existing=existing)
    password_enc = existing.password_enc if existing else ""
    if "password" in data:
        password_enc = encrypt_secret(data["password"] or "")
    values = {**clean, "password_enc": password_enc, "updated_by": actor_id[:200]}
    if existing is None:
        row = EmailSettings.objects.create(id=uuid.uuid4(), tenant_id=tenant_id, **values)
    else:
        EmailSettings.objects.filter(id=existing.id).update(updated_at=timezone.now(), **values)
        row = get_row(tenant_id)
    ok, error = check_connection(row)
    _record_test(row, ok, error)
    invalidate(tenant_id)
    record_platform_audit(
        actor_id=actor_id, action="platform.email_settings_updated", entity_type="EmailSettings", entity_id=str(row.id),
        correlation_id=correlation_id, tenant_id=tenant_id,
        metadata={"scope": "TENANT" if tenant_id else "PLATFORM", "host": row.host, "port": row.port,
                  "security": row.security, "enabled": row.enabled, "passwordChanged": "password" in data,
                  "testOk": ok},
    )
    return row


def delete(*, tenant_id=None, actor_id: str, correlation_id: str | None = None) -> None:
    tenant_id = _tenant_key(tenant_id)
    row = get_row(tenant_id)
    if row is None:
        return
    EmailSettings.objects.filter(id=row.id).delete()
    invalidate(tenant_id)
    record_platform_audit(
        actor_id=actor_id, action="platform.email_settings_deleted", entity_type="EmailSettings", entity_id=str(row.id),
        correlation_id=correlation_id, tenant_id=tenant_id,
        metadata={"scope": "TENANT" if tenant_id else "PLATFORM"},
    )


def send_test(*, tenant_id=None, to: str, actor_id: str, correlation_id: str | None = None) -> dict[str, Any]:
    """Envia uma mensagem real pela configuração gravada (mesmo que esteja inativa)."""
    tenant_id = _tenant_key(tenant_id)
    row = get_row(tenant_id)
    if row is None:
        raise EmailSettingsError("Ainda não há servidor de email configurado.")
    to = _clean_address(to, "O destinatário do teste", required=True)
    ok, error = True, ""
    try:
        message = EmailMessage(
            subject="Teste de email do Q360",
            body="Esta mensagem confirma que o Q360 consegue enviar email por este servidor. Pode ignorá-la.",
            from_email=formataddr((row.from_name, row.from_address)) if row.from_name else row.from_address,
            to=[to], reply_to=[row.reply_to] if row.reply_to else None, connection=_connection(row),
        )
        message.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        ok, error = False, f"{type(exc).__name__}: {exc}"[:500]
    _record_test(row, ok, error)
    invalidate(tenant_id)
    record_platform_audit(
        actor_id=actor_id, action="platform.email_settings_tested", entity_type="EmailSettings", entity_id=str(row.id),
        correlation_id=correlation_id, tenant_id=tenant_id, metadata={"ok": ok, "recipientDomain": to.split("@")[-1]},
    )
    return {"ok": ok, "error": error or None, "testedAt": row.last_test_at}
