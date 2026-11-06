"""Responsável de cada revisão: atribuir, atribuir em lote e saber quem pode decidir."""
from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.permissions import Permission, Role, effective_role_permissions
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.quote.domain.enums import ReviewTaskStatus
from apps.quote.domain.errors import QuoteStateError, ReferencedEntityNotFoundError, SegregationOfDutiesError
from apps.quote.infrastructure.models import Quote, ReviewTask

_audit = AuditService(DjangoAuditRepositoryAdapter())
_ACTIVE = (ReviewTaskStatus.OPEN.value, ReviewTaskStatus.IN_PROGRESS.value)
MAX_BATCH = 100


def decision_block_reason(quote: Quote, actor_id: str | None) -> str | None:
    """Regra dos quatro olhos: quem submeteu a cotação não a decide. Quem a criou
    pode decidi-la, desde que outra pessoa a tenha submetido."""
    if actor_id and quote.submitted_by == actor_id:
        return "Foi você que submeteu esta cotação; pela regra dos quatro olhos, a decisão tem de ser de outra pessoa"
    return None


def _reviewer_roles(tenant_id) -> set[str]:
    needed = {Permission.QUOTE_REVIEW, Permission.QUOTE_APPROVE}
    return {
        role.value for role, permissions in effective_role_permissions(tenant_id).items()
        if needed <= set(permissions) and role is not Role.PLATFORM_ADMIN
    }


def eligible_reviewers(quote: Quote) -> list[dict[str, str]]:
    from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole

    roles = _reviewer_roles(quote.tenant_id)
    account_ids = StaffAccountRole.objects.filter(role__in=roles).values_list("staff_account_id", flat=True)
    accounts = StaffAccount.objects.filter(id__in=account_ids, status=StaffAccount.ACTIVE).order_by("name")
    return [{"id": str(a.id), "name": a.name} for a in accounts if str(a.id) != quote.submitted_by]


def eligibility_report(quote: Quote) -> dict[str, Any]:
    reviewers = eligible_reviewers(quote)
    return {
        "eligibleReviewers": reviewers,
        "noEligibleReviewer": not reviewers,
        "alert": None if reviewers else (
            "Não existe nenhum revisor disponível além de quem submeteu esta cotação. "
            "Peça a um administrador que ative outra conta com este perfil."
        ),
    }


def _assignee(task: ReviewTask, assignee_id: uuid.UUID | None) -> str:
    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    if assignee_id is None or str(assignee_id) == actor_id:
        reason = decision_block_reason(task.quote, actor_id)
        if reason:
            raise SegregationOfDutiesError(reason)
        return actor_id
    if str(assignee_id) not in {row["id"] for row in eligible_reviewers(task.quote)}:
        raise ReferencedEntityNotFoundError("A pessoa indicada não pode rever esta cotação")
    return str(assignee_id)


def assign(*, task: ReviewTask, assignee_id: uuid.UUID | None) -> ReviewTask:
    if task.status not in _ACTIVE:
        raise QuoteStateError("Esta revisão já foi decidida")
    assignee = _assignee(task, assignee_id)
    updated = ReviewTask.objects.filter(id=task.id, status=task.status, row_version=task.row_version).update(
        assigned_to=assignee, status=ReviewTaskStatus.IN_PROGRESS.value,
        started_at=task.started_at or timezone.now(), row_version=task.row_version + 1,
    )
    if updated == 0:
        raise QuoteStateError("Esta revisão foi alterada entretanto; recarregue e tente de novo")
    task.refresh_from_db()
    _audit.record(
        action="quote.review_assigned", entity_type="Quote", entity_id=str(task.quote_id),
        metadata={"reviewTaskId": str(task.id), "assignedTo": assignee},
    )
    return task


def assign_many(*, task_ids: list[uuid.UUID], assignee_id: uuid.UUID | None) -> dict[str, list]:
    """Cada tarefa é tratada à parte: uma recusa não impede as restantes."""
    CurrentTenantProvider.require()
    tasks = {t.id: t for t in ReviewTask.objects.select_related("quote").filter(id__in=task_ids)}
    assigned: list[ReviewTask] = []
    failed: list[dict[str, str]] = []
    for task_id in dict.fromkeys(task_ids):
        task = tasks.get(task_id)
        if task is None:
            failed.append({"taskId": str(task_id), "reason": "Esta revisão não existe."})
            continue
        try:
            with transaction.atomic():
                assigned.append(assign(task=task, assignee_id=assignee_id))
        except DomainProblem as exc:
            failed.append({"taskId": str(task_id), "reason": str(exc)})
    return {"assigned": assigned, "failed": failed}


def staff_names(actor_ids) -> dict[str, str]:
    from apps.staff_accounts.infrastructure.models import StaffAccount

    valid = []
    for value in {a for a in actor_ids if a}:
        try:
            valid.append(uuid.UUID(str(value)))
        except ValueError:
            continue
    return {str(pk): name for pk, name in StaffAccount.objects.filter(id__in=valid).values_list("id", "name")}
