"""Notificações push do Portal Cliente (roadmap_mobile.md, Fase 1 — ponto 4).

- registo dos dispositivos (token do Expo) e preferências por categoria;
- envio quando se cria uma notificação do portal (`notifications_service.notify_account`),
  sempre depois do commit — como os emails — e nunca a falhar o pedido.

Privacidade: o texto de um push aparece no ecrã bloqueado, por isso leva só o
título da notificação e uma frase genérica; o detalhe (e qualquer dado de
saúde, p.ex. o motivo de uma recusa) só se vê dentro da app, depois de
desbloquear.
"""
from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.utils import timezone

from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.domain.push import CATEGORIES, PLATFORMS, category_of, is_enabled, is_expo_token
from apps.customer_portal.infrastructure import push_sender
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerPushDevice
from apps.foundation.application.context import CurrentTenantProvider

logger = logging.getLogger(__name__)

PUSH_BODY = "Toque para ver os detalhes."


class InvalidPushTokenError(ValueError):
    pass


def _tenant_id() -> uuid.UUID:
    return CurrentTenantProvider.require().value


# ---------------------------------------------------------- dispositivos
def register_device(
    *, account_id: uuid.UUID, session_id: uuid.UUID | None, expo_token: str, platform: str
) -> CustomerPushDevice:
    if not is_expo_token(expo_token):
        raise InvalidPushTokenError("Token de notificações inválido")
    platform = platform if platform in PLATFORMS else "OTHER"
    # O mesmo telemóvel pode passar de uma conta para outra (terminar sessão e
    # entrar com outro email): o token fica sempre com a conta que o registou por último.
    device, _ = CustomerPushDevice.objects.update_or_create(
        tenant_id=_tenant_id(), expo_token=expo_token,
        defaults={
            "customer_account_id": account_id, "device_session_id": session_id, "platform": platform,
            "active": True, "updated_at": timezone.now(),
        },
    )
    return device


def unregister_device(*, account_id: uuid.UUID, device_id: uuid.UUID) -> None:
    updated = CustomerPushDevice.objects.filter(id=device_id, customer_account_id=account_id).update(active=False)
    if not updated:
        raise PortalResourceNotFoundError("Dispositivo não encontrado")


# ----------------------------------------------------------- preferências
def get_preferences(account_id: uuid.UUID) -> list[dict]:
    stored = CustomerAccount.objects.filter(id=account_id).values_list("push_preferences", flat=True).first() or {}
    return [{"category": key, "label": label, "enabled": is_enabled(stored, key)} for key, label in CATEGORIES.items()]


def set_preferences(account_id: uuid.UUID, changes: dict[str, bool]) -> list[dict]:
    unknown = set(changes) - set(CATEGORIES)
    if unknown:
        raise ValueError(f"Categorias desconhecidas: {sorted(unknown)}")
    stored = dict(CustomerAccount.objects.filter(id=account_id).values_list("push_preferences", flat=True).first() or {})
    stored.update({key: bool(value) for key, value in changes.items()})
    CustomerAccount.objects.filter(id=account_id).update(push_preferences=stored)
    return get_preferences(account_id)


# ---------------------------------------------------------------- envio
def dispatch(
    *, tenant_id: uuid.UUID, account_id: uuid.UUID, notification_id: uuid.UUID, code: str, title: str,
    link: str | None,
) -> int:
    """Envia o push de uma notificação já gravada. Devolve quantos dispositivos
    foram contactados. Nunca levanta exceção."""
    try:
        if not settings.CUSTOMER_PORTAL_PUSH_ENABLED:
            return 0
        category = category_of(code)
        if category is None:
            return 0
        prefs = CustomerAccount.all_tenants.filter(tenant_id=tenant_id, id=account_id).values_list(
            "push_preferences", flat=True
        ).first()
        if not is_enabled(prefs, category):
            return 0
        devices = list(
            CustomerPushDevice.all_tenants.filter(tenant_id=tenant_id, customer_account_id=account_id, active=True)
        )
        if not devices:
            return 0
        messages = [
            {
                "to": device.expo_token, "title": title, "body": PUSH_BODY, "sound": "default",
                "channelId": "default",
                "data": {"notificationId": str(notification_id), "code": code, "link": link, "category": category},
            }
            for device in devices
        ]
        tickets = push_sender.post_messages(messages)
        dead = [
            device.id
            for device, ticket in zip(devices, tickets)
            if ticket.get("status") == "error" and (ticket.get("details") or {}).get("error") == "DeviceNotRegistered"
        ]
        if dead:
            # O Expo diz que o token já não existe (app desinstalada): deixa de se tentar.
            CustomerPushDevice.all_tenants.filter(id__in=dead).update(active=False, updated_at=timezone.now())
        return len(devices)
    except Exception:  # noqa: BLE001 - o push nunca pode estragar o pedido que o provocou
        logger.exception("Falha ao enviar a notificação push %s", notification_id)
        return 0
