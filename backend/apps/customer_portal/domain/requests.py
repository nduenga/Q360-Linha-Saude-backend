"""Regras puras dos pedidos ao seguro (PDF s.8): tipos, estados e transições.

Estados do PDF: Aberto → Em análise → Aguardando cliente → Aprovado/Rejeitado
→ Concluído. O cliente cria e responde; só o backoffice move o estado.
"""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem

OPEN = "OPEN"
IN_REVIEW = "IN_REVIEW"
AWAITING_CUSTOMER = "AWAITING_CUSTOMER"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
COMPLETED = "COMPLETED"

STATUS_LABELS = {
    OPEN: "Aberto",
    IN_REVIEW: "Em análise",
    AWAITING_CUSTOMER: "A aguardar o cliente",
    APPROVED: "Aprovado",
    REJECTED: "Rejeitado",
    COMPLETED: "Concluído",
}

# from -> allowed next states
TRANSITIONS: dict[str, frozenset[str]] = {
    OPEN: frozenset({IN_REVIEW, REJECTED}),
    IN_REVIEW: frozenset({AWAITING_CUSTOMER, APPROVED, REJECTED}),
    AWAITING_CUSTOMER: frozenset({IN_REVIEW, REJECTED}),
    APPROVED: frozenset({COMPLETED}),
    REJECTED: frozenset({COMPLETED}),
    COMPLETED: frozenset(),
}
OPEN_STATUSES = frozenset({OPEN, IN_REVIEW, AWAITING_CUSTOMER})
# A decision needs an explanation the customer can read.
NOTE_REQUIRED = frozenset({REJECTED, AWAITING_CUSTOMER})

# type -> (label, needs policy, needs quote, at most one open per target)
REQUEST_TYPES: dict[str, dict] = {
    "DATA_CHANGE": {"label": "Alteração de dados", "policy": False, "quote": False, "single": False},
    "MEMBER_INCLUSION": {"label": "Inclusão de beneficiário", "policy": True, "quote": False, "single": False},
    "MEMBER_EXCLUSION": {"label": "Exclusão de beneficiário", "policy": True, "quote": False, "single": False},
    "DOCUMENT_COPY": {"label": "Segunda via de documento", "policy": False, "quote": False, "single": False},
    "STATEMENT": {"label": "Declaração ou comprovativo", "policy": True, "quote": False, "single": False},
    "CONTACT_CHANGE": {"label": "Alteração de contactos", "policy": False, "quote": False, "single": False},
    "COVERAGE_QUESTION": {"label": "Esclarecimento sobre coberturas", "policy": False, "quote": False, "single": False},
    "RENEWAL": {"label": "Pedido de renovação", "policy": True, "quote": False, "single": True},
    "CANCELLATION": {"label": "Pedido de cancelamento", "policy": True, "quote": False, "single": True},
    "NEW_QUOTE": {"label": "Pedido de nova cotação", "policy": False, "quote": False, "single": False},
    "ACCEPT_QUOTE": {"label": "Aceitação de cotação", "policy": False, "quote": True, "single": True},
    "OTHER": {"label": "Outro pedido", "policy": False, "quote": False, "single": False},
}


# Pedidos que o cliente resolve sozinho no portal, sem esperar pelo GTE: o
# documento é gerado na hora a partir dos dados da apólice.
SELF_SERVICE: dict[str, str] = {
    "DOCUMENT_COPY": (
        "Descarregue a apólice em «Documentos» (GET /customer-portal/documents) e o cartão de cada pessoa segura "
        "em «Cartão»: não precisa de fazer um pedido."
    ),
    "STATEMENT": (
        "Descarregue a declaração de cobertura ou o comprovativo de pagamento em "
        "GET /customer-portal/policies/{policyNumber}/statement?kind=COVERAGE|PAYMENT: não precisa de fazer um pedido."
    ),
}


class PortalRequestInvalidError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class PortalRequestConflictError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


def assert_transition(current: str, target: str, note: str | None) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise PortalRequestConflictError(
            f"A request in {current} cannot move to {target}; allowed: {sorted(TRANSITIONS.get(current, ()))}"
        )
    if target in NOTE_REQUIRED and not (note or "").strip():
        raise PortalRequestInvalidError(f"A note for the customer is required when moving to {target}")
