"""Operações explícitas do ciclo de vida contratual.

Pagamentos continuam a ser registados manualmente. Este módulo aplica as
consequências contratuais desse registo; nunca assume que um débito bancário
ou uma notificação externa ocorreu.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.problem import DomainProblem
from apps.pricing.domain.money import round_amount
from apps.policy.domain.enums import EndorsementType, PolicyMemberStatus, PolicyStatus
from apps.policy.infrastructure.models import (
    Policy, PolicyEndorsement, PolicyMember, PolicySignature, PolicyStateHistory,
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
def resolve_policy_for_overdue_premium(
    *, policy: Policy, today: datetime.date | None = None, correlation_id: str | None = None
) -> bool:
    """Apply the legal resolution once the applicable premium is overdue."""
    today = today or timezone.localdate()
    locked = Policy.objects.select_for_update().get(id=policy.id)
    if locked.status == PolicyStatus.RESOLVED_BY_LAW.value:
        return False

    installment = (
        PremiumInstallment.objects.select_for_update()
        .filter(policy=locked, due_date__lt=today)
        .exclude(status__in=("PAID", "VOID"))
        .order_by("installment_no")
        .first()
    )
    if installment is None:
        return False
    if installment.status == "DUE":
        PremiumInstallment.objects.filter(id=installment.id, status="DUE").update(status="OVERDUE")

    if locked.status == PolicyStatus.PENDING_FIRST_PREMIUM.value and installment.installment_no == 1:
        signature = PolicySignature.objects.filter(policy=locked).first()
        if signature is None:
            raise PolicyLifecycleError(
                f"A apólice {locked.policy_number or locked.id} não tem assinatura para determinar a data efectiva da resolução"
            )
        reason_code = "INITIAL_PREMIUM"
        legal_basis = "ART_18_1"
        effective_from = signature.signed_at.date()
    elif (
        locked.status in (
            PolicyStatus.ACTIVE.value,
            PolicyStatus.SUSPENDED.value,
            PolicyStatus.EXPIRED.value,
        )
        and installment.installment_no > 1
        and (locked.end_date is None or installment.due_date <= locked.end_date)
    ):
        reason_code = "INSTALLMENT"
        legal_basis = "ART_18_3"
        effective_from = installment.due_date
    else:
        return False

    now = timezone.now()
    _history(
        locked,
        to_status=PolicyStatus.RESOLVED_BY_LAW.value,
        reason_code=reason_code,
        reason_text=f"Resolução automática por falta de pagamento ({legal_basis})",
        correlation_id=correlation_id,
    )
    updated = Policy.objects.filter(
        id=locked.id, status=locked.status, row_version=locked.row_version
    ).update(
        status=PolicyStatus.RESOLVED_BY_LAW.value,
        resolved_by_law=True,
        resolved_at=now,
        resolved_effective_from=effective_from,
        resolution_reason_code=reason_code,
        legal_basis=legal_basis,
        row_version=locked.row_version + 1,
    )
    if updated != 1:
        raise PolicyLifecycleError("A apólice foi alterada durante a resolução automática; tente novamente")
    return True


def resolve_overdue_policies(*, today: datetime.date | None = None) -> int:
    """Mark overdue instalments and resolve eligible policies idempotently."""
    today = today or timezone.localdate()
    mark_overdue(today=today)
    policy_ids = list(
        PremiumInstallment.objects.filter(status="OVERDUE", due_date__lt=today)
        .values_list("policy_id", flat=True)
        .distinct()
    )
    return sum(
        resolve_policy_for_overdue_premium(
            policy=Policy(id=policy_id), today=today
        )
        for policy_id in policy_ids
    )


def calculate_resolution_refund(policy: Policy) -> dict:
    """Return an estimated unpaid-refund amount; no refund is recorded as paid."""
    if not policy.resolved_by_law or not policy.resolved_effective_from:
        return {
            "amount": None,
            "period_start": None,
            "period_end": None,
            "status": "NOT_APPLICABLE",
        }

    paid = list(
        PremiumInstallment.objects.filter(policy=policy, status="PAID").order_by("period_from")
    )
    if policy.resolution_reason_code == "INITIAL_PREMIUM":
        amount = sum((item.amount for item in paid), Decimal("0"))
        ends = [item.period_to for item in paid]
        if amount <= 0:
            return {"amount": round_amount(Decimal("0")), "period_start": None, "period_end": None, "status": "NOT_DUE"}
        return {
            "amount": round_amount(amount),
            "period_start": policy.resolved_effective_from,
            "period_end": max(ends) if ends else policy.end_date,
            "status": "ESTIMATED",
        }

    refundable = Decimal("0")
    refund_starts: list[datetime.date] = []
    refund_ends: list[datetime.date] = []
    first_unused_day = policy.resolved_effective_from + datetime.timedelta(days=1)
    for installment in paid:
        unused_start = max(installment.period_from, first_unused_day)
        if unused_start > installment.period_to:
            continue
        total_days = (installment.period_to - installment.period_from).days + 1
        unused_days = (installment.period_to - unused_start).days + 1
        if total_days <= 0:
            continue
        refundable += installment.amount * Decimal(unused_days) / Decimal(total_days)
        refund_starts.append(unused_start)
        refund_ends.append(installment.period_to)

    return {
        "amount": round_amount(refundable),
        "period_start": min(refund_starts) if refund_starts else None,
        "period_end": max(refund_ends) if refund_ends else None,
        "status": "ESTIMATED" if refundable > 0 else "NOT_DUE",
    }


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
    if installment_no < 1:
        raise PolicyLifecycleError("O número da prestação é inválido")
    resolve_policy_for_overdue_premium(policy=policy, correlation_id=correlation_id)
    policy.refresh_from_db()
    if policy.status != PolicyStatus.RESOLVED_BY_LAW.value:
        raise PolicyLifecycleError("Não existe prestação vencida elegível para resolução automática")
    return policy


@transaction.atomic
def terminate_for_default(*, policy: Policy, installment_no: int, correlation_id: str | None) -> Policy:
    if installment_no < 1:
        raise PolicyLifecycleError("O número da prestação é inválido")
    resolve_policy_for_overdue_premium(policy=policy, correlation_id=correlation_id)
    policy.refresh_from_db()
    if policy.status != PolicyStatus.RESOLVED_BY_LAW.value:
        raise PolicyLifecycleError("Não existe prestação vencida elegível para resolução automática")
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
