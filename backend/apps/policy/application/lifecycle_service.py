"""Operações explícitas do ciclo de vida contratual.

Pagamentos continuam a ser registados manualmente. Este módulo aplica as
consequências contratuais desse registo; nunca assume que um débito bancário
ou uma notificação externa ocorreu.
"""
from __future__ import annotations

import datetime

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.problem import DomainProblem
from apps.policy.domain.enums import EndorsementType, PolicyMemberStatus, PolicyStatus
from apps.policy.infrastructure.models import (
    Policy, PolicyEndorsement, PolicyMember, PolicyStateHistory,
    PremiumDefaultNotice, PremiumInstallment,
)


class PolicyLifecycleError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _actor_id() -> str:
    actor = CurrentActorProvider.get()
    return actor.actor_id if actor else "system"


def _history(policy: Policy, *, to_status: str, reason_code: str, reason_text: str | None, correlation_id: str | None) -> None:
    PolicyStateHistory.objects.create(
        tenant_id=policy.tenant_id, policy=policy, from_status=policy.status,
        to_status=to_status, reason_code=reason_code, reason_text=reason_text,
        changed_by=_actor_id(), correlation_id=correlation_id,
    )


def mark_overdue(*, today: datetime.date | None = None) -> int:
    """Idempotently persists the date-derived overdue state."""
    today = today or timezone.localdate()
    return PremiumInstallment.objects.filter(status="DUE", due_date__lt=today).update(status="OVERDUE")


@transaction.atomic
def register_default_notice(*, policy: Policy, installment_no: int, registered_mail_reference: str,
                            new_deadline: datetime.date, sent_at: datetime.datetime | None = None) -> PremiumDefaultNotice:
    installment = PremiumInstallment.objects.select_for_update().filter(policy=policy, installment_no=installment_no).first()
    if installment is None:
        raise PolicyLifecycleError("A prestação indicada não existe nesta apólice")
    mark_overdue(today=(sent_at or timezone.now()).date())
    installment.refresh_from_db()
    if installment.status != "OVERDUE":
        raise PolicyLifecycleError("Só pode enviar carta registada para uma prestação vencida e não paga")
    if new_deadline <= (sent_at or timezone.now()).date():
        raise PolicyLifecycleError("O novo prazo da carta tem de ser posterior à data de envio")
    if installment.default_notices.filter(outcome__isnull=True).exists():
        raise PolicyLifecycleError("Já existe uma carta de incumprimento aberta para esta prestação")
    return PremiumDefaultNotice.objects.create(
        tenant_id=policy.tenant_id, installment=installment, sent_at=sent_at or timezone.now(),
        registered_mail_reference=registered_mail_reference.strip(), new_deadline=new_deadline,
        registered_by=_actor_id(),
    )


@transaction.atomic
def suspend_for_default(*, policy: Policy, installment_no: int, correlation_id: str | None) -> Policy:
    if policy.status != PolicyStatus.ACTIVE.value:
        raise PolicyLifecycleError("Só uma apólice ativa pode ser suspensa")
    notice = PremiumDefaultNotice.objects.select_for_update().filter(
        installment__policy=policy, installment__installment_no=installment_no, outcome__isnull=True,
        new_deadline__lt=timezone.localdate(),
    ).order_by("-sent_at").first()
    if notice is None:
        raise PolicyLifecycleError("A suspensão exige carta registada cujo novo prazo já tenha terminado")
    _history(policy, to_status=PolicyStatus.SUSPENDED.value, reason_code="PREMIUM_DEFAULT", reason_text=None,
             correlation_id=correlation_id)
    Policy.objects.filter(id=policy.id, status=PolicyStatus.ACTIVE.value).update(
        status=PolicyStatus.SUSPENDED.value, row_version=policy.row_version + 1
    )
    notice.outcome = "SUSPENDED"
    notice.suspension_effective_at = timezone.now()
    notice.save(update_fields=["outcome", "suspension_effective_at"])
    policy.refresh_from_db()
    return policy


@transaction.atomic
def terminate_for_default(*, policy: Policy, installment_no: int, correlation_id: str | None) -> Policy:
    if policy.status != PolicyStatus.SUSPENDED.value:
        raise PolicyLifecycleError("A apólice tem de estar suspensa antes de ser resolvida por incumprimento")
    notice = PremiumDefaultNotice.objects.select_for_update().filter(
        installment__policy=policy, installment__installment_no=installment_no, outcome="SUSPENDED",
        new_deadline__lt=timezone.localdate(),
    ).order_by("-sent_at").first()
    if notice is None:
        raise PolicyLifecycleError("Não existe carta de incumprimento elegível para resolver esta apólice")
    _history(policy, to_status=PolicyStatus.TERMINATED.value, reason_code="PREMIUM_DEFAULT", reason_text=None,
             correlation_id=correlation_id)
    Policy.objects.filter(id=policy.id, status=PolicyStatus.SUSPENDED.value).update(
        status=PolicyStatus.TERMINATED.value, termination_reason_code="PREMIUM_DEFAULT",
        terminated_at=timezone.now(), row_version=policy.row_version + 1,
    )
    notice.outcome = "TERMINATED"
    notice.save(update_fields=["outcome"])
    policy.refresh_from_db()
    return policy


@transaction.atomic
def reactivate_after_regularization(*, policy: Policy, correlation_id: str | None) -> Policy:
    """A reativação só vale para o futuro e só depois de liquidar todos os atrasos."""
    if policy.status != PolicyStatus.SUSPENDED.value:
        return policy
    if PremiumInstallment.objects.filter(policy=policy, status__in=("DUE", "OVERDUE"), due_date__lte=timezone.localdate()).exists():
        return policy
    _history(policy, to_status=PolicyStatus.ACTIVE.value, reason_code="PREMIUM_REGULARIZED", reason_text=None,
             correlation_id=correlation_id)
    Policy.objects.filter(id=policy.id, status=PolicyStatus.SUSPENDED.value).update(
        status=PolicyStatus.ACTIVE.value, row_version=policy.row_version + 1
    )
    policy.refresh_from_db()
    return policy


@transaction.atomic
def cancel_policy(*, policy: Policy, reason_code: str, reason_text: str | None, effective_date: datetime.date,
                  correlation_id: str | None) -> Policy:
    if policy.status not in (PolicyStatus.PENDING_FIRST_PREMIUM.value, PolicyStatus.ACTIVE.value, PolicyStatus.SUSPENDED.value):
        raise PolicyLifecycleError("O estado atual da apólice não permite cancelamento")
    if effective_date < timezone.localdate():
        raise PolicyLifecycleError("O cancelamento não pode produzir efeitos retroativos")
    _history(policy, to_status=PolicyStatus.CANCELLED.value, reason_code=reason_code, reason_text=reason_text,
             correlation_id=correlation_id)
    Policy.objects.filter(id=policy.id).update(
        status=PolicyStatus.CANCELLED.value, cancellation_reason_code=reason_code,
        cancellation_effective_date=effective_date, cancelled_by=_actor_id(), cancelled_at=timezone.now(),
        row_version=policy.row_version + 1,
    )
    policy.refresh_from_db()
    return policy


@transaction.atomic
def exclude_member(*, policy: Policy, member_id, effective_date: datetime.date, reason: str, correlation_id: str | None) -> PolicyMember:
    if policy.status not in (PolicyStatus.ACTIVE.value, PolicyStatus.SUSPENDED.value):
        raise PolicyLifecycleError("Só pode excluir beneficiários de uma apólice ativa ou suspensa")
    if effective_date < timezone.localdate():
        raise PolicyLifecycleError("A exclusão não pode produzir efeitos retroativos")
    member = PolicyMember.objects.select_for_update().filter(policy=policy, member_id=member_id,
        status=PolicyMemberStatus.ACTIVE.value, exclusion_date__isnull=True).first()
    if member is None:
        raise PolicyLifecycleError("A pessoa não é um beneficiário ativo desta apólice")
    PolicyMember.objects.filter(id=member.id).update(status=PolicyMemberStatus.EXCLUDED.value,
        exclusion_date=effective_date, row_version=member.row_version + 1)
    no = (PolicyEndorsement.objects.filter(policy=policy).aggregate(top=Max("endorsement_number"))["top"] or 0) + 1
    PolicyEndorsement.objects.create(tenant_id=policy.tenant_id, policy=policy, endorsement_number=no,
        endorsement_type=EndorsementType.EXCLUDE_MEMBER.value, effective_date=effective_date,
        payload_json={"memberId": str(member_id), "reason": reason}, created_by=_actor_id())
    member.refresh_from_db()
    return member


def expire_policies(*, today: datetime.date | None = None, correlation_id: str | None = None) -> int:
    today = today or timezone.localdate()
    total = 0
    for policy in Policy.objects.filter(status=PolicyStatus.ACTIVE.value, end_date__lt=today):
        with transaction.atomic():
            _history(policy, to_status=PolicyStatus.EXPIRED.value, reason_code="TERM_ENDED", reason_text=None,
                     correlation_id=correlation_id)
            total += Policy.objects.filter(id=policy.id, status=PolicyStatus.ACTIVE.value).update(
                status=PolicyStatus.EXPIRED.value, row_version=policy.row_version + 1
            )
    return total
