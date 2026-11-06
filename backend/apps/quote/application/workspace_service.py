"""Cotação numa só página: uma chamada guarda o rascunho, verifica a
elegibilidade e recalcula o prémio; a resposta traz tudo o que a página mostra.

Uma falha de cálculo não perde nada: as alterações ficam guardadas e a resposta
explica o que aconteceu, para o utilizador poder tentar de novo.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from django.db import transaction

from apps.foundation.domain.problem import DomainProblem
from apps.quote.application import quote_service, requirements_service, simulator_service
from apps.quote.domain.enums import QuoteStatus
from apps.quote.domain.errors import QuoteStateError, RowVersionMismatchError
from apps.quote.infrastructure.models import Quote, QuoteMember
from shared.status_labels import status_label

_EDITABLE = (QuoteStatus.DRAFT.value, QuoteStatus.READY.value)


def _members(quote: Quote) -> list[dict[str, Any]]:
    rows = quote.members.select_related("member", "eligibility_evaluation").order_by("created_at", "id")
    return [
        {
            "memberId": str(row.member_id),
            "name": " ".join(part for part in (row.member.first_name, row.member.last_name) if part) or None,
            "relationshipCode": row.member.relationship_code,
            "dateOfBirth": row.member.date_of_birth,
            "status": row.status,
            "eligibilityDecision": row.eligibility_evaluation.decision if row.eligibility_evaluation else None,
        }
        for row in rows
    ]


def _check(code: str, label: str, passed: bool, *, blocking: bool = True, detail: str | None = None) -> dict[str, Any]:
    return {"code": code, "label": label, "passed": passed, "blocking": blocking, "detail": detail}


def readiness(quote: Quote, requirements: dict[str, Any], members: list[dict[str, Any]]) -> dict[str, Any]:
    """Checklist «Pronto para revisão?»: bloqueios e avisos antes de enviar."""
    proposer = quote.proposer
    included = [m for m in members if m["status"] != "EXCLUDED"]
    questionnaires = [w for w in requirements["warnings"] if w["code"] == "CLINICAL_QUESTIONNAIRE_REQUIRED"]
    checks = [
        _check("CLIENT_CONTACT", "Cliente e contactos completos", bool(proposer.email or proposer.phone)),
        _check("ELIGIBILITY", f"Elegibilidade verificada ({len(included)}/{len(members)})", bool(included)),
        _check("PREMIUM", "Prémio calculado", quote.status == QuoteStatus.READY.value and quote.latest_pricing_run_id is not None),
        _check(
            "UNDERWRITING_RULES", "Regras de subscrição cumpridas", not requirements["blocking"],
            detail="; ".join(e["message"] for e in requirements["errors"]) or None,
        ),
        _check(
            "CLINICAL_QUESTIONNAIRE", "Questionários clínicos preenchidos", not questionnaires, blocking=False,
            detail=", ".join(w.get("memberName") or "" for w in questionnaires) or None,
        ),
    ]
    return {"ready": all(c["passed"] for c in checks if c["blocking"]), "checks": checks}


def snapshot(quote: Quote, *, render: Callable, pricing_error: str | None = None) -> dict[str, Any]:
    quote = Quote.objects.select_related("proposer", "plan__product", "latest_pricing_run").get(id=quote.id)
    members = _members(quote)
    requirements = requirements_service.evaluate_requirements(quote)
    run = quote.latest_pricing_run
    return {
        "quoteId": str(quote.id),
        "quoteNumber": quote.quote_number,
        "status": quote.status,
        "statusLabel": status_label("quote", quote.status),
        "rowVersion": quote.row_version,
        "savedAt": quote.updated_at,
        "selection": quote.selection_json,
        "members": members,
        "premium": render(run) if run is not None and run.total_amount is not None else None,
        "pricingError": pricing_error,
        "requirements": {"errors": requirements["errors"], "warnings": requirements["warnings"]},
        "readiness": readiness(quote, requirements, members),
    }


def sync(
    *, quote: Quote, member_ids: list[uuid.UUID], selection: dict[str, Any] | None, row_version: int,
    correlation_id: str | None, render: Callable,
) -> dict[str, Any]:
    if quote.status not in _EDITABLE:
        raise QuoteStateError("Esta cotação já não pode ser alterada")
    if quote.row_version != row_version:
        raise RowVersionMismatchError(f"A versão desta cotação ({row_version}) não coincide com a versão atual; recarregue e tente de novo")

    current = set(QuoteMember.objects.filter(quote=quote).values_list("member_id", flat=True))
    wanted = list(dict.fromkeys(member_ids))
    to_remove = current - set(wanted)
    to_add = [member_id for member_id in wanted if member_id not in current]
    with transaction.atomic():
        for member_id in to_remove:
            quote_service.remove_quote_member(quote=quote, member_id=member_id)
            quote.refresh_from_db()
        for member_id in to_add:
            quote = quote_service.add_quote_member(quote=quote, member_id=member_id, correlation_id=correlation_id)

    selection_changed = selection is not None and selection != quote.selection_json
    pricing_error = None
    try:
        if selection_changed:
            quote, warnings = simulator_service.set_selection(quote=quote, selection=selection, row_version=quote.row_version)
            pricing_error = next((w["message"] for w in warnings if w["code"] == "PRODUCT_INPUT_INCOMPLETE"), None)
        quote.refresh_from_db()
        needs_pricing = quote.status == QuoteStatus.DRAFT.value and wanted and pricing_error is None
        if needs_pricing:
            quote_service.price_quote(quote=quote, recalculate=True, correlation_id=correlation_id)
    except DomainProblem as exc:
        pricing_error = str(exc)
    quote.refresh_from_db()
    return snapshot(quote, render=render, pricing_error=pricing_error)
