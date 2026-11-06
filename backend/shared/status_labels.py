"""Vocabulário único de estados, por entidade (Manual visual v2, cap. 22).

Os valores técnicos da API não mudam. Este catálogo diz como cada estado se
chama em filtros, etiquetas, notificações e relatórios, pela ordem do ciclo.
`RETURNED` e `ACCEPTED` não existem na coluna `quote.status`: são estados de
apresentação, derivados do histórico da cotação e dos pedidos de aceitação.
"""
from __future__ import annotations

STATUS_DICTIONARY: dict[str, list[tuple[str, str]]] = {
    "quote": [
        ("DRAFT", "Rascunho"),
        ("READY", "Calculada"),
        ("IN_REVIEW", "Em revisão"),
        ("RETURNED", "Devolvida"),
        ("APPROVED", "Aprovada"),
        ("ACCEPTED", "Aceite"),
        ("REJECTED", "Rejeitada"),
        ("EXPIRED", "Expirada"),
        ("CANCELLED", "Cancelada"),
        ("BOUND", "Emitida"),
    ],
    "policy": [
        ("PENDING_FIRST_PREMIUM", "Pendente"),
        ("ACTIVE", "Ativa"),
        ("SUSPENDED", "Suspensa"),
        ("CANCELLED", "Cancelada"),
        ("TERMINATED", "Terminada"),
        ("RESOLVED_BY_LAW", "Resolvida por lei"),
        ("EXPIRED", "Vencida"),
        ("RENEWED", "Renovada"),
    ],
    "installment": [
        ("DUE", "A aguardar"),
        ("PAID", "Paga"),
        ("OVERDUE", "Em atraso"),
        ("VOID", "Anulada"),
    ],
    "portalRequest": [
        ("OPEN", "Novo"),
        ("IN_REVIEW", "Em tratamento"),
        ("AWAITING_CUSTOMER", "A aguardar cliente"),
        ("APPROVED", "Aprovado"),
        ("REJECTED", "Rejeitado"),
        ("COMPLETED", "Concluído"),
    ],
    "configuration": [
        ("DRAFT", "Rascunho"),
        ("PENDING_APPROVAL", "A aguardar 2.º aprovador"),
        ("APPROVED", "Aprovada"),
        ("PUBLISHED", "Publicada"),
        ("REJECTED", "Rejeitada"),
    ],
    "reviewTask": [
        ("OPEN", "Por atribuir"),
        ("IN_PROGRESS", "Em tratamento"),
        ("DECIDED", "Decidida"),
        ("RETURNED", "Devolvida"),
    ],
    "questionnaire": [
        ("NOT_STARTED", "Por preencher"),
        ("IN_PROGRESS", "Em preenchimento"),
        ("COMPLETED", "Concluído"),
    ],
}

_LABELS = {entity: dict(rows) for entity, rows in STATUS_DICTIONARY.items()}


def status_label(entity: str, status: str | None) -> str | None:
    """Nome de um estado; um valor desconhecido devolve-se tal como está."""
    if status is None:
        return None
    return _LABELS[entity].get(status, status)


def status_dictionary() -> dict[str, list[dict[str, str]]]:
    return {
        entity: [{"status": status, "label": label} for status, label in rows]
        for entity, rows in STATUS_DICTIONARY.items()
    }
