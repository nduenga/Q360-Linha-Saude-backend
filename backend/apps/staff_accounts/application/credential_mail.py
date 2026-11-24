"""Emails de credenciais do staff e da plataforma: palavra-passe temporária
(nova conta ou reposição) e ligação de recuperação.

Os emails saem depois do commit (uma transação revertida não envia nada) e
uma falha no envio nunca desfaz a operação: fica no log e na auditoria.
Reutiliza `send_mail`/`sender` do portal (mesmo servidor de email), importados
só aqui dentro para este módulo não depender do resto do portal em tempo de
importação."""
from __future__ import annotations

import logging
from urllib.parse import quote

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def login_url() -> str:
    return f"{settings.Q360_PLATFORM_URL}/login"


def reset_url(token: str) -> str:
    return f"{settings.Q360_PLATFORM_URL}/redefinir-password?token={quote(token, safe='')}"


def _deliver(*, subject: str, body: str, to_email: str, tenant_name: str | None, audit_entity: str,
             audit_id: str, what: str, tenant_id=None) -> None:
    from apps.customer_portal.infrastructure.email_sender import send_mail, sender
    from apps.platform_admin.application.audit_service import record_platform_audit

    def _send() -> None:
        try:
            send_mail(subject=subject, message=body, from_email=sender(tenant_name), recipient_list=[to_email],
                      fail_silently=False)
        except Exception as exc:  # noqa: BLE001 - o email não pode desfazer a operação
            logger.exception("Falha ao enviar o email «%s» para a conta %s", what, audit_id)
            record_platform_audit(actor_id="SYSTEM", action=f"platform.{what}_email_failed", entity_type=audit_entity,
                                  entity_id=audit_id, metadata={"reason": type(exc).__name__}, tenant_id=tenant_id)
        else:
            record_platform_audit(actor_id="SYSTEM", action=f"platform.{what}_email_sent", entity_type=audit_entity,
                                  entity_id=audit_id, tenant_id=tenant_id)

    transaction.on_commit(_send)


def send_welcome_email(*, to_email: str, name: str, password: str, tenant_name: str | None, account_id: str,
                       tenant_id=None, entity: str = "StaffAccount") -> None:
    """Conta nova (primeiro administrador, administrador adicional ou utilizador criado com palavra-passe gerada)."""
    where = f"da {tenant_name}" if tenant_name else "da plataforma"
    body = (
        f"Olá {name},\n\n"
        f"Foi criada a sua conta no Q360, {where}.\n\n"
        f"Endereço: {login_url()}\n"
        f"Email: {to_email}\n"
        f"Palavra-passe temporária: {password}\n\n"
        "Entre e altere a palavra-passe assim que puder. Se a esquecer, use «Esqueci-me da palavra-passe» "
        "no ecrã de entrada.\n\n"
        "Se não esperava este email, contacte a equipa responsável."
    )
    _deliver(subject="A sua conta no Q360", body=body, to_email=to_email, tenant_name=tenant_name,
             audit_entity=entity, audit_id=account_id, what="credentials", tenant_id=tenant_id)


def send_password_reset_email(*, to_email: str, name: str, password: str, tenant_name: str | None, account_id: str,
                              tenant_id=None, entity: str = "StaffAccount") -> None:
    """Reposição feita por um administrador: a nova palavra-passe vai por email."""
    body = (
        f"Olá {name},\n\n"
        "A sua palavra-passe do Q360 foi reposta por um administrador.\n\n"
        f"Endereço: {login_url()}\n"
        f"Nova palavra-passe temporária: {password}\n\n"
        "Entre e altere-a assim que puder. Se não pediu esta reposição, contacte o administrador da sua conta."
    )
    _deliver(subject="A sua palavra-passe do Q360 foi reposta", body=body, to_email=to_email,
             tenant_name=tenant_name, audit_entity=entity, audit_id=account_id, what="password_reset",
             tenant_id=tenant_id)


def send_recovery_email(*, to_email: str, name: str, token: str, tenant_name: str | None, account_id: str,
                        ttl_minutes: int, tenant_id=None, entity: str = "StaffAccount") -> None:
    """Recuperação pedida pelo próprio utilizador: ligação de uso único e curta duração."""
    body = (
        f"Olá {name},\n\n"
        "Recebemos um pedido para repor a sua palavra-passe do Q360.\n\n"
        f"Para escolher uma nova, abra: {reset_url(token)}\n\n"
        f"A ligação expira em {ttl_minutes} minutos e só pode ser usada uma vez. "
        "Se não foi você, ignore este email: a sua palavra-passe não muda."
    )
    _deliver(subject="Recuperar a palavra-passe do Q360", body=body, to_email=to_email, tenant_name=tenant_name,
             audit_entity=entity, audit_id=account_id, what="password_recovery", tenant_id=tenant_id)
