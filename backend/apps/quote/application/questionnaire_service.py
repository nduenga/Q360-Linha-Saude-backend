"""Questionário clínico: preencher por secções, guardar o progresso e concluir.

Pode ser preenchido pela equipa ou, a pedido dela, pelo cliente no Portal. O
conteúdo é dado de saúde: a auditoria só regista quem fez o quê, nunca as
respostas.
"""
from __future__ import annotations

import uuid
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.quote.domain import clinical_questionnaire as form
from apps.quote.domain.enums import QuoteStatus
from apps.quote.domain.errors import QuoteStateError, ReferencedEntityNotFoundError, RowVersionMismatchError
from apps.quote.infrastructure.models import ClinicalQuestionnaire, Quote, QuoteMember
from shared.status_labels import status_label

_audit = AuditService(DjangoAuditRepositoryAdapter())
_EDITABLE = (QuoteStatus.DRAFT.value, QuoteStatus.READY.value, QuoteStatus.IN_REVIEW.value)
NOT_STARTED = "NOT_STARTED"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
STAFF = "STAFF"
CUSTOMER = "CUSTOMER"


class QuestionnaireInvalidError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class QuestionnaireIncompleteError(DomainProblem):
    http_status = 409
    problem_code = "QUESTIONNAIRE-INCOMPLETE"


def _actor_id() -> str:
    actor = CurrentActorProvider.get()
    return actor.actor_id if actor else "unknown"


def _quote_member(quote: Quote, member_id: uuid.UUID) -> QuoteMember:
    row = QuoteMember.objects.select_related("member").filter(quote=quote, member_id=member_id).first()
    if row is None:
        raise ReferencedEntityNotFoundError(f"A pessoa segura {member_id} não pertence a esta cotação")
    return row


def _require_editable(quote: Quote) -> None:
    if quote.status not in _EDITABLE:
        raise QuoteStateError("O questionário só pode ser alterado até a cotação ser decidida")


def _member_name(member) -> str:
    return " ".join(part for part in (member.first_name, member.last_name) if part) or "Pessoa segura"


def _definition(row: ClinicalQuestionnaire | None = None) -> dict[str, Any]:
    """A resposta usa sempre a cópia da versão com que foi iniciada."""
    if row and row.schema_json:
        return form.schema(row.schema_json)
    if row:
        return form.schema()
    from apps.business_config.application.readers import BusinessSnapshot
    return form.schema(BusinessSnapshot.load().get("underwriting.clinical_questionnaire"))


def _summary(quote_member: QuoteMember, row: ClinicalQuestionnaire | None) -> dict[str, Any]:
    answers = row.answers_json if row else {}
    definition = _definition(row)
    status = row.status if row else NOT_STARTED
    return {
        "questionnaireId": str(row.id) if row else None,
        "quoteId": str(quote_member.quote_id),
        "memberId": str(quote_member.member_id),
        "memberName": _member_name(quote_member.member),
        "status": status,
        "statusLabel": status_label("questionnaire", status),
        "progress": form.progress(answers, definition),
        "currentSection": row.current_section if row else None,
        "hasDeclarations": form.has_declarations(answers, definition),
        "requestedFromCustomerAt": row.requested_from_customer_at if row else None,
        "updatedAt": row.updated_at if row else None,
        "updatedChannel": row.updated_channel if row else None,
        "completedAt": row.completed_at if row else None,
        "rowVersion": row.row_version if row else None,
    }


def statuses_for_quote(quote: Quote) -> dict[str, str]:
    return {
        str(member_id): status
        for member_id, status in ClinicalQuestionnaire.objects.filter(quote=quote).values_list("member_id", "status")
    }


def list_for_quote(quote: Quote) -> list[dict[str, Any]]:
    rows = {row.member_id: row for row in ClinicalQuestionnaire.objects.filter(quote=quote)}
    members = QuoteMember.objects.select_related("member").filter(quote=quote).order_by("created_at", "id")
    return [_summary(member, rows.get(member.member_id)) for member in members]


def detail(quote: Quote, member_id: uuid.UUID) -> dict[str, Any]:
    quote_member = _quote_member(quote, member_id)
    row = ClinicalQuestionnaire.objects.filter(quote=quote, member_id=member_id).first()
    _audit.record(
        action="clinical_questionnaire.viewed", entity_type="Quote", entity_id=str(quote.id),
        metadata={"memberId": str(member_id)},
    )
    return {
        **_summary(quote_member, row),
        "schema": _definition(row),
        "answers": row.answers_json if row else {},
    }


def _create(quote: Quote, member_id: uuid.UUID, *, channel: str, **fields: Any) -> ClinicalQuestionnaire:
    definition = fields.pop("definition", None) or _definition()
    try:
        with transaction.atomic():
            return ClinicalQuestionnaire.objects.create(
                tenant_id=quote.tenant_id, quote=quote, member_id=member_id,
                schema_version=definition["version"], schema_json=definition,
                updated_by=_actor_id(), updated_channel=channel, **fields,
            )
    except IntegrityError as exc:
        raise RowVersionMismatchError("Outra pessoa acabou de guardar este questionário; recarregue e tente de novo") from exc


def save(
    *, quote: Quote, member_id: uuid.UUID, answers: dict[str, Any], current_section: str | None,
    row_version: int | None, channel: str = STAFF,
) -> dict[str, Any]:
    """Guarda um preenchimento parcial. Alterar um questionário concluído volta
    a abri-lo, para ninguém decidir com base em respostas por confirmar."""
    _require_editable(quote)
    quote_member = _quote_member(quote, member_id)
    if current_section is not None and current_section not in form.section_keys(_definition(ClinicalQuestionnaire.objects.filter(quote=quote, member_id=member_id).first())):
        raise QuestionnaireInvalidError(f"A secção «{current_section}» não existe neste questionário.")
    row = ClinicalQuestionnaire.objects.filter(quote=quote, member_id=member_id).first()
    if channel == CUSTOMER:
        if row is None or row.requested_from_customer_at is None:
            raise QuoteStateError("A seguradora não pediu este questionário ao cliente")
        if row.status == COMPLETED:
            raise QuoteStateError("Este questionário já foi concluído")
    try:
        merged = form.merge_answers(row.answers_json if row else {}, answers, _definition(row))
    except form.QuestionnaireAnswerError as exc:
        raise QuestionnaireInvalidError(str(exc)) from exc

    if row is None:
        row = _create(quote, member_id, channel=channel, answers_json=merged, current_section=current_section, definition=_definition(row))
    else:
        if row_version is None:
            raise QuestionnaireInvalidError("Indique a versão (rowVersion) do questionário que está a alterar.")
        updated = ClinicalQuestionnaire.objects.filter(id=row.id, row_version=row_version).update(
            answers_json=merged, current_section=current_section or row.current_section, status=IN_PROGRESS,
            completed_at=None, completed_by=None, updated_by=_actor_id(), updated_channel=channel,
            updated_at=timezone.now(), row_version=row_version + 1,
        )
        if updated == 0:
            raise RowVersionMismatchError("Este questionário foi alterado entretanto; recarregue e tente de novo")
        row.refresh_from_db()
    _audit.record(
        action="clinical_questionnaire.saved", entity_type="Quote", entity_id=str(quote.id),
        metadata={"memberId": str(member_id), "channel": channel},
    )
    return {**_summary(quote_member, row), "answers": row.answers_json}


def complete(*, quote: Quote, member_id: uuid.UUID, row_version: int, channel: str = STAFF) -> dict[str, Any]:
    _require_editable(quote)
    quote_member = _quote_member(quote, member_id)
    row = ClinicalQuestionnaire.objects.filter(quote=quote, member_id=member_id).first()
    if row is None:
        raise QuestionnaireIncompleteError("Este questionário ainda não tem respostas")
    if channel == CUSTOMER and row.requested_from_customer_at is None:
        raise QuoteStateError("A seguradora não pediu este questionário ao cliente")
    missing = form.missing_labels(row.answers_json, _definition(row))
    if missing:
        raise QuestionnaireIncompleteError("Faltam respostas obrigatórias: " + "; ".join(missing))
    actor_id = _actor_id()
    updated = ClinicalQuestionnaire.objects.filter(id=row.id, row_version=row_version, status=IN_PROGRESS).update(
        status=COMPLETED, completed_at=timezone.now(), completed_by=actor_id, updated_by=actor_id,
        updated_channel=channel, updated_at=timezone.now(), row_version=row_version + 1,
    )
    if updated == 0:
        raise RowVersionMismatchError("Este questionário foi alterado entretanto; recarregue e tente de novo")
    row.refresh_from_db()
    _audit.record(
        action="clinical_questionnaire.completed", entity_type="Quote", entity_id=str(quote.id),
        metadata={"memberId": str(member_id), "channel": channel},
    )
    return {**_summary(quote_member, row), "answers": row.answers_json}


def request_from_customer(*, quote: Quote, member_id: uuid.UUID) -> dict[str, Any]:
    """Abre o questionário ao cliente no Portal e avisa-o."""
    from apps.customer_portal.application import notifications_service

    _require_editable(quote)
    quote_member = _quote_member(quote, member_id)
    accounts = notifications_service.account_ids_for_proposer(quote.proposer_id)
    if not accounts:
        raise QuoteStateError("Este cliente ainda não tem acesso ao Portal; preencha o questionário com ele")
    actor_id = _actor_id()
    row = ClinicalQuestionnaire.objects.filter(quote=quote, member_id=member_id).first()
    now = timezone.now()
    if row is None:
        row = _create(quote, member_id, channel=STAFF, requested_from_customer_at=now, requested_by=actor_id)
    elif row.status == COMPLETED:
        raise QuoteStateError("Este questionário já está concluído")
    else:
        ClinicalQuestionnaire.objects.filter(id=row.id).update(
            requested_from_customer_at=now, requested_by=actor_id, updated_at=now, row_version=row.row_version + 1,
        )
        row.refresh_from_db()
    name = _member_name(quote_member.member)
    for account_id in accounts:
        notifications_service.notify_account(
            account_id=account_id, dedupe_key=f"questionnaire:{row.id}:REQUESTED", code="QUESTIONNAIRE_REQUESTED",
            title=f"Preencha o questionário clínico de {name}",
            body=f"A cotação {quote.quote_number} precisa deste questionário para seguir.",
            link=f"/portal/cotacoes/{quote.quote_number}/questionario/{member_id}",
        )
    _audit.record(
        action="clinical_questionnaire.requested", entity_type="Quote", entity_id=str(quote.id),
        metadata={"memberId": str(member_id)},
    )
    return _summary(quote_member, row)


def pending_for_customer(quotes) -> list[dict[str, Any]]:
    rows = (
        ClinicalQuestionnaire.objects.select_related("quote", "member")
        .filter(quote__in=quotes, quote__status__in=_EDITABLE, requested_from_customer_at__isnull=False, status=IN_PROGRESS)
        .order_by("requested_from_customer_at")
    )
    return [
        {
            "quoteNumber": row.quote.quote_number,
            "memberId": str(row.member_id),
            "memberName": _member_name(row.member),
            "progress": form.progress(row.answers_json, _definition(row)),
            "requestedAt": row.requested_from_customer_at,
        }
        for row in rows
    ]
