"""Só para dados de demonstração: recua uma apólice inteira no tempo.

Os seeds precisam de prestações «em atraso» ou «a vencer em breve». Mudar só o
vencimento deixava dados impossíveis (prestação em atraso de um período que
ainda não começou, paga antes do início da apólice). Aqui recua-se tudo junto
— vigência, prestações, pagamentos e inclusões — e o cenário fica coerente.
"""
from __future__ import annotations

import datetime

from apps.policy.infrastructure.models import Policy, PolicyMember, PremiumInstallment


def _shift_iso(value, delta: datetime.timedelta):
    try:
        return (datetime.date.fromisoformat(value) - delta).isoformat()
    except (TypeError, ValueError):
        return value


def backdate_policy(policy: Policy, days: int) -> None:
    """Recua em `days` dias todas as datas da apólice (negativo = avança)."""
    if not days:
        return
    delta = datetime.timedelta(days=days)
    Policy.all_tenants.filter(id=policy.id).update(
        start_date=policy.start_date - delta if policy.start_date else None,
        end_date=policy.end_date - delta if policy.end_date else None,
    )
    for row in PremiumInstallment.all_tenants.filter(policy_id=policy.id):
        PremiumInstallment.all_tenants.filter(id=row.id).update(
            period_from=row.period_from - delta, period_to=row.period_to - delta, due_date=row.due_date - delta,
            paid_at=row.paid_at - delta if row.paid_at else None,
        )
    for member in PolicyMember.all_tenants.filter(policy_id=policy.id):
        PolicyMember.all_tenants.filter(id=member.id).update(
            inclusion_date=member.inclusion_date - delta if member.inclusion_date else None,
            waiting_period_ends_json={k: _shift_iso(v, delta) for k, v in (member.waiting_period_ends_json or {}).items()},
        )


def make_installment_late(policy: Policy, installment_no: int, *, days_late: int) -> None:
    """A prestação `installment_no` passa a ter começado há `days_late` dias e fica por pagar."""
    row = PremiumInstallment.all_tenants.get(policy_id=policy.id, installment_no=installment_no)
    target = datetime.date.today() - datetime.timedelta(days=days_late)
    backdate_policy(policy, (row.period_from - target).days)
    PremiumInstallment.all_tenants.filter(policy_id=policy.id, installment_no=installment_no).update(
        status="OVERDUE", paid_at=None)


def make_installment_due_soon(policy: Policy, installment_no: int, *, in_days: int) -> None:
    """A prestação `installment_no` vence daqui a `in_days` dias (as anteriores mantêm-se pagas)."""
    row = PremiumInstallment.all_tenants.get(policy_id=policy.id, installment_no=installment_no)
    target = datetime.date.today() + datetime.timedelta(days=in_days)
    backdate_policy(policy, (row.period_from - target).days)
    PremiumInstallment.all_tenants.filter(policy_id=policy.id, installment_no=installment_no).update(
        status="DUE", paid_at=None)
