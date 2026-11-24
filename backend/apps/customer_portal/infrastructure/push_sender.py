"""Envio pelo Expo Push Service (gratuito): https://docs.expo.dev/push-notifications/sending-notifications/

Nunca levanta exceção: uma notificação push perdida não pode estragar o pedido
que a provocou (a central de notificações do portal continua a ter tudo).
Devolve um «ticket» por mensagem, pela mesma ordem; em caso de falha, lista vazia.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_MAX_BATCH = 100  # limite do Expo por pedido


def post_messages(messages: list[dict]) -> list[dict]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if settings.CUSTOMER_PORTAL_EXPO_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {settings.CUSTOMER_PORTAL_EXPO_ACCESS_TOKEN}"
    tickets: list[dict] = []
    for start in range(0, len(messages), _MAX_BATCH):
        batch = messages[start : start + _MAX_BATCH]
        try:
            response = requests.post(
                settings.CUSTOMER_PORTAL_EXPO_PUSH_URL, json=batch, headers=headers,
                timeout=settings.CUSTOMER_PORTAL_PUSH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json().get("data") or []
        except (requests.RequestException, ValueError):
            logger.exception("Falha ao enviar %s notificações push pelo Expo", len(batch))
            data = [{}] * len(batch)  # sem resposta: mantém o alinhamento com as mensagens
        tickets.extend(data)
    return tickets
