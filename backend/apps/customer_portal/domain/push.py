"""Categorias de notificações push. O cliente liga/desliga por categoria nas
preferências do perfil; cada código de notificação do portal pertence a uma.
Códigos fora desta tabela (p.ex. apólice emitida) ficam só na central do
portal — não geram push."""
from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "PAYMENTS": "Pagamentos",
    "QUOTES": "Cotações e propostas",
    "REQUESTS": "Pedidos",
    "MESSAGES": "Mensagens",
    "POLICIES": "Apólices, endossos e renovação",
}

CODE_CATEGORY: dict[str, str] = {
    "PAYMENT_OVERDUE": "PAYMENTS",
    "PAYMENT_PENDING": "PAYMENTS",
    "QUOTE_APPROVED": "QUOTES",
    "QUOTE_REJECTED": "QUOTES",
    "QUESTIONNAIRE_REQUESTED": "QUOTES",
    "REQUEST_UPDATED": "REQUESTS",
    "MEMBER_DOCUMENT_REVIEWED": "REQUESTS",
    "NEW_MESSAGE": "MESSAGES",
    "RENEWAL_AVAILABLE": "POLICIES",
    "POLICY_EXPIRING": "POLICIES",
    "ENDORSEMENT_PENDING": "POLICIES",
}

PLATFORMS = ("IOS", "ANDROID", "WEB", "OTHER")


def category_of(code: str) -> str | None:
    return CODE_CATEGORY.get(code)


def is_enabled(preferences: dict | None, category: str) -> bool:
    """Omitido = ligado: só se guarda o que o cliente desligou ou voltou a ligar."""
    return bool((preferences or {}).get(category, True))


def is_expo_token(value: str) -> bool:
    return (value.startswith("ExponentPushToken[") or value.startswith("ExpoPushToken[")) and value.endswith("]")
