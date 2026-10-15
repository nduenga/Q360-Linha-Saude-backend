"""Análise dos documentos em falta e ativação das pessoas seguras.

Fluxo:
  1. A elegibilidade deixa uma pessoa `PENDING_DOCUMENT` (ex.: falta o certificado
     de matrícula de um filho com mais de 18 anos). Na cotação fica `REFERRAL`;
     na apólice fica `PENDING` (sem cobertura).
  2. Cliente (portal) ou GTE enviam o documento (`member_document_service`).
  3. O GTE **aprova** ou **recusa** o documento (`review_document`).
  4. Ao aprovar, a pessoa é reavaliada (`reevaluate_member`): se agora cumpre as
     regras, passa a elegível na cotação e **ativa** na apólice, com início de
     cobertura e carências calculados, e fica registado um endosso `ACTIVATE_MEMBER`.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.client.application import member_document_service
from apps.client.domain.errors import MemberDocumentStateError
from apps.client.domain.member_documents import EVIDENCE_LABELS, DocumentStatus, requirement_for_reason
from apps.client.infrastructure.models import InsuredMember, MemberDocument
from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.policy.application import issuance_service
from apps.policy.domain.enums import EndorsementType, PolicyMemberStatus, PolicyStatus
from apps.policy.infrastructure.models import PolicyEndorsement, PolicyMember
from apps.quote.application import quote_service
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import QuoteMember

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()

_OPEN_QUOTE_STATUSES = (QuoteStatus.DRAFT.value, QuoteStatus.READY.value, QuoteStatus.IN_REVIEW.value)
_LIVE_POLICY_STATUSES = (
    PolicyStatus.PENDING_FIRST_PREMIUM.value,
    PolicyStatus.ACTIVE.value,
    PolicyStatus.SUSPENDED.value,
)


def _first_code(evaluation) -> str | None:
    evidence = evaluation.evidence_json or []
    return evidence[0].get("code") if evidence else None


def pending_requirements(member: InsuredMember) -> list[dict[str, Any]]:
    """O que falta enviar para esta pessoa ficar coberta, nas cotações abertas e
    nas apólices em que está pendente."""
    items: list[dict[str, Any]] = []
    for pm in PolicyMember.objects.filter(member=member, status=PolicyMemberStatus.PENDING.value).select_related("policy"):
        requirement = requirement_for_reason(pm.pending_reason_code)
        message = None
        if pm.eligibility_evaluation is not None and pm.eligibility_evaluation.evidence_json:
            message = pm.eligibility_evaluation.evidence_json[0].get("message")
        items.append(
            {
                "context": "POLICY",
                "reference": pm.policy.policy_number,
                "reasonCode": pm.pending_reason_code,
                "message": message,
                "documentType": requirement["documentType"] if requirement else None,
                "documentLabel": requirement["documentLabel"] if requirement else None,
                "needsDocument": requirement is not None,
            }
        )
    quote_members = QuoteMember.objects.filter(
        member=member, status="REFERRAL", quote__status__in=_OPEN_QUOTE_STATUSES
    ).select_related("quote", "eligibility_evaluation")
    for qm in quote_members:
        code = _first_code(qm.eligibility_evaluation) if qm.eligibility_evaluation else None
        requirement = requirement_for_reason(code)
        message = qm.eligibility_evaluation.evidence_json[0].get("message") if qm.eligibility_evaluation and qm.eligibility_evaluation.evidence_json else None
        items.append(
            {
                "context": "QUOTE",
                "reference": qm.quote.quote_number,
                "reasonCode": code,
                "message": message,
                "documentType": requirement["documentType"] if requirement else None,
                "documentLabel": requirement["documentLabel"] if requirement else None,
                "needsDocument": requirement is not None,
            }
        )
    return items


def reevaluate_member(*, member: InsuredMember, correlation_id: str | None) -> dict[str, list[dict[str, Any]]]:
    """Reavalia a pessoa onde está pendente e aplica o resultado."""
    report: dict[str, list[dict[str, Any]]] = {"quoteMembers": [], "policyMembers": []}
    today = timezone.now().date()
    actor_id = _actor_id()

    for qm in QuoteMember.objects.filter(member=member, quote__status__in=_OPEN_QUOTE_STATUSES).select_related("quote"):
        evaluation = EvaluateEligibilityUseCase().execute(
            proposer_id=qm.quote.proposer_id,
            member_id=member.id,
            plan_id=qm.quote.plan_id,
            effective_date=qm.quote.reference_date,
            context={},
            correlation_id=correlation_id,
        )
        new_status = quote_service._ELIGIBILITY_TO_MEMBER_STATUS[evaluation.decision]
        changed = qm.status != new_status
        QuoteMember.objects.filter(id=qm.id).update(status=new_status, eligibility_evaluation=evaluation)
        if changed:
            quote_service._demote_to_draft_if_ready(qm.quote)
        report["quoteMembers"].append(
            {"quoteNumber": qm.quote.quote_number, "from": qm.status, "to": new_status, "decision": evaluation.decision}
        )

    pending = PolicyMember.objects.filter(
        member=member, status=PolicyMemberStatus.PENDING.value, policy__status__in=_LIVE_POLICY_STATUSES
    ).select_related("policy", "policy__source_quote")
    for pm in pending:
        policy = pm.policy
        evaluation = EvaluateEligibilityUseCase().execute(
            proposer_id=policy.proposer_id,
            member_id=member.id,
            plan_id=policy.plan_id,
            effective_date=policy.start_date or policy.source_quote.reference_date,
            context={},
            correlation_id=correlation_id,
        )
        new_status = issuance_service._ELIGIBILITY_TO_POLICY_MEMBER_STATUS.get(evaluation.decision)
        entry = {"policyNumber": policy.policy_number, "from": pm.status, "decision": evaluation.decision}
        if new_status == PolicyMemberStatus.ACTIVE.value:
            with transaction.atomic():
                PolicyMember.objects.filter(id=pm.id).update(
                    status=PolicyMemberStatus.ACTIVE.value,
                    pending_reason_code=None,
                    eligibility_evaluation=evaluation,
                    rule_version=evaluation.rule_version,
                    row_version=pm.row_version + 1,
                )
                pm.refresh_from_db()
                if policy.status == PolicyStatus.ACTIVE.value:
                    # A cobertura começa hoje e as carências contam a partir daí.
                    PolicyMember.objects.filter(id=pm.id).update(
                        inclusion_date=today,
                        waiting_period_ends_json=issuance_service._waiting_period_ends(
                            policy=policy, policy_member=pm, inclusion_date=today
                        ),
                    )
                number = (PolicyEndorsement.objects.filter(policy=policy).aggregate(top=Max("endorsement_number"))["top"] or 0) + 1
                PolicyEndorsement.objects.create(
                    tenant_id=policy.tenant_id,
                    policy=policy,
                    endorsement_number=number,
                    endorsement_type=EndorsementType.ACTIVATE_MEMBER.value,
                    effective_date=today,
                    payload_json={"memberId": str(member.id), "evaluationId": str(evaluation.id)},
                    created_by=actor_id,
                )
            _audit.record(
                action="policy.member_activated",
                entity_type="Policy",
                entity_id=str(policy.id),
                correlation_id=correlation_id,
                metadata={"memberId": str(member.id), "endorsementNo": number},
            )
            _outbox.append(
                aggregate_type="Policy",
                aggregate_id=str(policy.id),
                event_type="POLICY.MEMBER.ACTIVATED",
                correlation_id=correlation_id,
                payload={"policyId": str(policy.id), "policyNumber": policy.policy_number, "memberId": str(member.id)},
            )
            entry.update(to=PolicyMemberStatus.ACTIVE.value, endorsementNo=number)
        elif new_status == PolicyMemberStatus.PENDING.value:
            PolicyMember.objects.filter(id=pm.id).update(
                pending_reason_code=_first_code(evaluation), eligibility_evaluation=evaluation, rule_version=evaluation.rule_version
            )
            entry.update(to=PolicyMemberStatus.PENDING.value, stillMissing=_first_code(evaluation))
        else:
            entry.update(to=pm.status, note="A pessoa continua sem cumprir as regras de elegibilidade do plano.")
        report["policyMembers"].append(entry)
    return report


def review_document(
    *, document: MemberDocument, decision: str, note: str | None, correlation_id: str | None
) -> dict[str, Any]:
    if document.status != DocumentStatus.SUBMITTED.value:
        raise MemberDocumentStateError(f"O documento já foi analisado (estado {document.status})")
    if decision not in ("APPROVE", "REJECT"):
        raise MemberDocumentStateError("A decisão tem de ser APPROVE ou REJECT")
    if decision == "REJECT" and not (note or "").strip():
        raise MemberDocumentStateError("Ao recusar um documento tem de explicar o motivo (note)")

    actor_id = _actor_id()
    new_status = DocumentStatus.APPROVED.value if decision == "APPROVE" else DocumentStatus.REJECTED.value
    with transaction.atomic():
        updated = MemberDocument.objects.filter(id=document.id, status=DocumentStatus.SUBMITTED.value).update(
            status=new_status, reviewed_by=actor_id, reviewed_at=timezone.now(), review_note=(note or "").strip() or None
        )
        if updated == 0:
            raise MemberDocumentStateError("O documento foi analisado entretanto; recarregue")
        document.refresh_from_db()
        report = reevaluate_member(member=document.member, correlation_id=correlation_id) if decision == "APPROVE" else None

    _audit.record(
        action="member_document.reviewed",
        entity_type="MemberDocument",
        entity_id=str(document.id),
        correlation_id=correlation_id,
        metadata={"memberId": str(document.member_id), "decision": decision},
    )
    _outbox.append(
        aggregate_type="MemberDocument",
        aggregate_id=str(document.id),
        event_type="MEMBER.DOCUMENT.REVIEWED",
        correlation_id=correlation_id,
        payload={"documentId": str(document.id), "memberId": str(document.member_id), "decision": decision},
    )
    _notify_customers(document, decision=decision, note=note, activated=bool(report and report["policyMembers"] and any(p.get("to") == "ACTIVE" for p in report["policyMembers"])))
    return {"document": member_document_service.serialize(document), "reevaluation": report}


def _notify_customers(document: MemberDocument, *, decision: str, note: str | None, activated: bool) -> None:
    from apps.customer_portal.application import notifications_service, requests_service

    member = document.member
    name = " ".join(p for p in (member.first_name, member.last_name) if p) or "a pessoa segura"
    label = EVIDENCE_LABELS.get(document.evidence_type, "documento")
    if decision == "APPROVE":
        title = f"Documento aceite: {label}"
        body = f"O documento de {name} foi aceite." + (" A cobertura já está ativa." if activated else "")
    else:
        title = f"Documento recusado: {label}"
        body = f"O documento de {name} foi recusado. Motivo: {(note or '').strip()}. Pode enviar outro."
    for account_id in requests_service.linked_account_ids(member.proposer_id):
        notifications_service.notify_account(
            account_id=account_id,
            dedupe_key=f"memberdoc:{document.id}:{decision}",
            code="MEMBER_DOCUMENT_REVIEWED",
            title=title,
            body=body,
            link=f"/portal/beneficiarios/{member.id}",
        )


def _actor_id() -> str:
    from apps.foundation.application.context import CurrentActorProvider

    actor = CurrentActorProvider.get()
    return actor.actor_id if actor else "system"
