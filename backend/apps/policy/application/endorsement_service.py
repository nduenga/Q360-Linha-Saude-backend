"""Endosso de inclusão: pessoas que entram numa apólice ativa a meio do
período, pagando só a parte do ano que falta (pro-rata).

Fluxo (decisões de negócio de 2026-10-22):
  1. A partir da apólice ACTIVE cria-se uma cotação `ENDORSEMENT` ligada a
     ela, com a **data de inclusão** escolhida antes de calcular. Não se
     aceitam datas no passado, nem fora do período da apólice.
  2. A cotação de endosso só tem as pessoas novas. A tarifa, as idades e as
     regras são as da data de inclusão (`Quote.reference_date`). As pessoas
     já seguras não são recalculadas.
  3. Cálculo: prémio anual das pessoas novas × dias até ao fim da apólice ÷
     base dos dias (por omissão os dias reais do período: 366 num ano
     bissexto); prémio mínimo configurável; o valor é repartido pelas
     prestações que ainda vão vencer, com o encargo de fracionamento da
     periodicidade da apólice (configurável).
  4. Submissão à subscrição (o cálculo fica congelado). Recém-nascidos dentro
     da janela configurada entram automaticamente: sem questionário clínico e
     sem revisão manual.
  5. Aprovada, a proposta segue para o cliente, com prazo de aceitação
     configurável. Aceite: as pessoas entram na apólice na data de inclusão,
     com carências a contar dessa data, fica registado o endosso ADD_MEMBER e
     são criadas as prestações do endosso. Recusada ou fora de prazo: a apólice
     não muda.

Configuração do tenant: `policy.endorsements` (interface)."""
from __future__ import annotations

from shared import formatting as fmt

import datetime
import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.business_config.application.readers import BusinessSnapshot
from apps.client.infrastructure.models import InsuredMember, RelationshipCode
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import require_reason
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.policy.domain.enums import EndorsementType, PolicyMemberStatus, PolicyStatus
from apps.policy.infrastructure.models import Policy, PolicyEndorsement, PolicyMember, PremiumInstallment
from apps.pricing.domain.money import round_amount
from apps.quote.domain.enums import QuoteStatus, ReviewTaskStatus
from apps.quote.infrastructure.models import Quote, QuoteMember, ReviewTask

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()

ENDORSEMENT = "ENDORSEMENT"
CONFIG_KEY = "policy.endorsements"
DAY_BASES = ("ACTUAL_PERIOD", "FIXED_366", "FIXED_365", "FIXED_360")
DEFAULTS: dict[str, Any] = {
    "day_count_basis": "ACTUAL_PERIOD",
    "minimum_premium": "0",
    "apply_fractionation_loading": True,
    "newborn_auto_inclusion_days": 0,
    "acceptance_days": 30,
    # A parte do período entre a inclusão e o início da próxima prestação por
    # pagar já está coberta pelas prestações pagas: IMMEDIATE cobra-a logo
    # (vence na data de inclusão), SPREAD reparte-a pelas prestações futuras.
    "prepaid_period_charge": "IMMEDIATE",
}
NEWBORN_APPROVER = "system:newborn-auto-inclusion"
_OPEN_STATUSES = ("DRAFT", "READY", "IN_REVIEW", "APPROVED")
_SETTLED_INSTALLMENT_STATUSES = ("PAID", "CANCELLED")


class EndorsementError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class EndorsementStateError(DomainProblem):
    http_status = 409
    problem_code = "QUOTE-STATE"


class EndorsementNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


# ------------------------------------------------------------- configuração
def settings(on: datetime.date | None = None) -> dict[str, Any]:
    raw = BusinessSnapshot.load(on).get(CONFIG_KEY) or {}
    result = dict(DEFAULTS)
    for key in DEFAULTS:
        if raw.get(key) not in (None, ""):
            result[key] = raw[key]
    if result["day_count_basis"] not in DAY_BASES:
        result["day_count_basis"] = DEFAULTS["day_count_basis"]
    if result["prepaid_period_charge"] not in ("IMMEDIATE", "SPREAD"):
        result["prepaid_period_charge"] = DEFAULTS["prepaid_period_charge"]
    return result


def _today() -> datetime.date:
    return timezone.localdate()


def _actor_id() -> str:
    actor = CurrentActorProvider.get()
    return actor.actor_id if actor else "unknown"


# ---------------------------------------------------------------- validações
def _active_policy(policy_id) -> Policy:
    policy = Policy.objects.select_related("plan", "proposer", "source_quote").filter(id=policy_id).first()
    if policy is None:
        raise EndorsementNotFoundError(f"A apólice {policy_id} não existe neste tenant")
    if policy.status != PolicyStatus.ACTIVE.value or policy.start_date is None or policy.end_date is None:
        raise EndorsementStateError(
            f"A apólice {policy.policy_number} está em {policy.status}; só se incluem pessoas numa apólice ativa (ACTIVE)"
        )
    return policy


def _check_inclusion_date(policy: Policy, inclusion: datetime.date) -> None:
    today = _today()
    if inclusion < today:
        raise EndorsementError(
            f"A data de inclusão ({fmt.date(inclusion)}) não pode ser anterior a hoje ({fmt.date(today)})"
        )
    if inclusion < policy.start_date or inclusion > policy.end_date:
        raise EndorsementError(
            f"A data de inclusão tem de estar dentro do período da apólice "
            f"({fmt.date(policy.start_date)} a {fmt.date(policy.end_date)})"
        )


def policy_of(quote: Quote) -> Policy:
    policy = Policy.objects.select_related("plan", "source_quote").filter(id=quote.source_policy_id).first()
    if policy is None:
        raise EndorsementNotFoundError(f"A apólice do endosso {quote.id} não existe")
    return policy


def require_endorsement(quote: Quote) -> None:
    if quote.quote_type != ENDORSEMENT:
        raise EndorsementStateError(f"A cotação {quote.id} não é um endosso")


def assert_member_can_join(quote: Quote, member: InsuredMember) -> None:
    """Chamado ao juntar uma pessoa a uma cotação de endosso: não pode já
    estar segura (ou pendente) na apólice."""
    if quote.quote_type != ENDORSEMENT:
        return
    if PolicyMember.objects.filter(
        policy_id=quote.source_policy_id, member_id=member.id, exclusion_date__isnull=True,
        status__in=(PolicyMemberStatus.ACTIVE.value, PolicyMemberStatus.PENDING.value),
    ).exists():
        raise EndorsementError(f"A pessoa {member.id} já está na apólice; o endosso é só para pessoas novas")


# ------------------------------------------------------------------ criação
def create_inclusion(*, policy_id, inclusion_date: datetime.date, member_ids: list, correlation_id: str | None) -> Quote:
    from apps.quote.application import quote_service

    policy = _active_policy(policy_id)
    _check_inclusion_date(policy, inclusion_date)
    if Quote.objects.filter(source_policy_id=policy.id, quote_type=ENDORSEMENT, status__in=_OPEN_STATUSES).exists():
        raise EndorsementStateError(
            f"A apólice {policy.policy_number} já tem um endosso em curso; conclua-o ou cancele-o primeiro"
        )
    with transaction.atomic():
        quote = quote_service.create_quote(proposer_id=policy.proposer_id, plan_id=policy.plan_id)
        Quote.objects.filter(id=quote.id).update(
            quote_type=ENDORSEMENT,
            source_policy_id=policy.id,
            selection_json=policy.source_quote.selection_json or {},
            endorsement_json={
                "kind": "INCLUSION",
                "policyId": str(policy.id),
                "policyNumber": policy.policy_number,
                "inclusionDate": inclusion_date.isoformat(),
                "policyPeriod": {"start": policy.start_date.isoformat(), "end": policy.end_date.isoformat()},
                "paymentFrequency": policy.payment_frequency,
            },
        )
        quote.refresh_from_db()
        for member_id in member_ids:
            quote = quote_service.add_quote_member(quote=quote, member_id=member_id, correlation_id=correlation_id)
    _audit.record(
        action="policy.endorsement_started", entity_type="Policy", entity_id=str(policy.id),
        correlation_id=correlation_id,
        metadata={"quoteId": str(quote.id), "inclusionDate": inclusion_date.isoformat(),
                  "memberIds": [str(m) for m in member_ids]},
    )
    return _try_price(quote)


def _try_price(quote: Quote) -> Quote:
    from apps.quote.application import quote_service

    if not quote.members.exists():
        return quote
    try:
        quote_service.price_quote(quote=quote, recalculate=True, correlation_id=None)
    except DomainProblem:
        pass  # o cálculo pode falhar por configuração; o utilizador vê o erro ao calcular
    quote.refresh_from_db()
    return quote


def set_inclusion_date(*, quote: Quote, inclusion_date: datetime.date) -> Quote:
    """A data de inclusão (= data de referência do cálculo) pode mudar até à
    submissão; a elegibilidade das pessoas é reavaliada nessa data."""
    from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
    from apps.quote.application import quote_service

    require_endorsement(quote)
    if quote.status not in (QuoteStatus.DRAFT.value, QuoteStatus.READY.value):
        raise EndorsementStateError("A data de inclusão só muda antes da submissão (DRAFT ou READY)")
    policy = _active_policy(quote.source_policy_id)
    _check_inclusion_date(policy, inclusion_date)
    with transaction.atomic():
        data = {**(quote.endorsement_json or {}), "inclusionDate": inclusion_date.isoformat()}
        Quote.objects.filter(id=quote.id).update(endorsement_json=data)
        quote.refresh_from_db()
        quote_service._demote_to_draft_if_ready(quote)
        for qm in quote.members.all():
            evaluation = EvaluateEligibilityUseCase().execute(
                proposer_id=quote.proposer_id, member_id=qm.member_id, plan_id=quote.plan_id,
                effective_date=inclusion_date, context={}, correlation_id=None,
            )
            QuoteMember.objects.filter(id=qm.id).update(
                eligibility_evaluation=evaluation,
                status=quote_service._ELIGIBILITY_TO_MEMBER_STATUS[evaluation.decision],
            )
    _audit.record(action="quote.endorsement_date_changed", entity_type="Quote", entity_id=str(quote.id),
                  metadata={"inclusionDate": inclusion_date.isoformat()})
    return _try_price(quote)


# ------------------------------------------------------------------- cálculo
def _inclusion_date(quote: Quote) -> datetime.date:
    raw = (quote.endorsement_json or {}).get("inclusionDate")
    if not raw:
        raise EndorsementError("O endosso não tem data de inclusão")
    return datetime.date.fromisoformat(raw)


def _age_on(birth: datetime.date | None, on: datetime.date) -> int | None:
    if birth is None:
        return None
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def _is_newborn(member: InsuredMember, inclusion: datetime.date, window_days: int, categories: dict) -> bool:
    if window_days <= 0 or member.date_of_birth is None:
        return False
    if categories.get(member.relationship_code) != "CHILD":
        return False
    days = (inclusion - member.date_of_birth).days
    return 0 <= days <= window_days


def newborn_members(quote: Quote) -> set[str]:
    """Pessoas do endosso que são recém-nascidos dentro da janela configurada."""
    if quote.quote_type != ENDORSEMENT:
        return set()
    window = int(settings(quote.reference_date).get("newborn_auto_inclusion_days") or 0)
    if window <= 0:
        return set()
    inclusion = _inclusion_date(quote)
    categories = dict(RelationshipCode.objects.values_list("code", "category"))
    return {
        str(qm.member_id) for qm in quote.members.select_related("member")
        if _is_newborn(qm.member, inclusion, window, categories)
    }


def _day_basis(code: str, policy: Policy) -> int:
    if code == "FIXED_366":
        return 366
    if code == "FIXED_365":
        return 365
    if code == "FIXED_360":
        return 360
    return (policy.end_date - policy.start_date).days + 1


def _future_due_installments(policy: Policy, inclusion: datetime.date) -> list[PremiumInstallment]:
    """Uma linha por data de vencimento ainda por vir (a partir da inclusão):
    é por essas datas que o endosso se reparte.

    `due_date__lte=policy.end_date` é uma validação defensiva: uma
    prestação vencer depois do fim da apólice não devia poder acontecer
    (nunca se fatura cobertura que já não existe), mas se os dados da
    apólice ficarem inconsistentes com o seu próprio calendário de
    prestações — por exemplo, `end_date` alterado sem recalcular as
    prestações — mostrar essa prestação "órfã" produzia um documento de
    inclusão com datas de dois períodos diferentes ao mesmo tempo. Sem
    nenhuma prestação válida dentro do período, cai-se no ramo `else` de
    `calculate()`: uma prestação única, a vencer na própria data de
    inclusão, com o período até ao fim real da apólice — o resultado
    correto para esse caso."""
    seen: set[datetime.date] = set()
    result = []
    for row in (policy.installments.filter(due_date__gte=inclusion, due_date__lte=policy.end_date)
                .exclude(status__in=_SETTLED_INSTALLMENT_STATUSES).order_by("due_date", "installment_no")):
        if row.due_date in seen:
            continue
        seen.add(row.due_date)
        result.append(row)
    return result


def calculate(quote: Quote) -> dict[str, Any]:
    """Cálculo do endosso a partir do último cálculo da cotação (prémio anual
    das pessoas novas na data de inclusão)."""
    from apps.policy.application.issuance_service import fractionation_loading

    require_endorsement(quote)
    policy = policy_of(quote)
    inclusion = _inclusion_date(quote)
    config = settings(inclusion)
    run = quote.latest_pricing_run
    if run is None or run.total_amount is None:
        raise EndorsementStateError("Calcule primeiro o prémio das pessoas novas (POST /quotes/{id}/price)")
    annual = round_amount(run.total_amount)
    remaining = (policy.end_date - inclusion).days + 1
    basis = _day_basis(config["day_count_basis"], policy)
    factor = Decimal(remaining) / Decimal(basis)
    pro_rata = round_amount(annual * factor)
    minimum = round_amount(Decimal(str(config["minimum_premium"] or "0")))
    premium = max(pro_rata, minimum)

    due = _future_due_installments(policy, inclusion)
    frequency = policy.payment_frequency
    split = len(due) >= 1
    loading = Decimal("0")
    if split and config["apply_fractionation_loading"] and frequency != "ANUAL":
        loading = fractionation_loading(quote, frequency)
    total_charged = round_amount(premium * (Decimal("1") + loading))
    installments = []
    if split:
        to_spread = total_charged
        first_future = min(row.period_from for row in due)
        if config["prepaid_period_charge"] == "IMMEDIATE" and first_future > inclusion:
            # Sem isto o cliente ficava coberto desde a inclusão e só pagava a
            # partir da próxima prestação (p.ex. 6 meses depois, se as
            # prestações seguintes já estavam pagas).
            gap_days = (first_future - inclusion).days
            upfront = round_amount(total_charged * Decimal(gap_days) / Decimal(remaining))
            if upfront > 0:
                installments.append({"sequence": 1, "dueDate": inclusion.isoformat(), "periodFrom": inclusion.isoformat(),
                                     "periodTo": (first_future - datetime.timedelta(days=1)).isoformat(),
                                     "amount": str(upfront)})
                to_spread = round_amount(total_charged - upfront)
        offset = len(installments)
        each = round_amount(to_spread / len(due))
        for index, row in enumerate(due, start=1):
            amount = each if index < len(due) else round_amount(to_spread - each * (len(due) - 1))
            installments.append({"sequence": offset + index, "dueDate": row.due_date.isoformat(),
                                 "periodFrom": max(row.period_from, inclusion).isoformat(),
                                 "periodTo": row.period_to.isoformat(), "amount": str(amount)})
    else:
        installments.append({"sequence": 1, "dueDate": inclusion.isoformat(), "periodFrom": inclusion.isoformat(),
                             "periodTo": policy.end_date.isoformat(), "amount": str(total_charged)})

    window = int(config.get("newborn_auto_inclusion_days") or 0)
    categories = dict(RelationshipCode.objects.values_list("code", "category"))
    members = []
    for qm in quote.members.select_related("member", "eligibility_evaluation").order_by("created_at"):
        m = qm.member
        members.append({
            "memberId": str(m.id),
            "name": " ".join(p for p in (m.first_name, m.last_name) if p) or None,
            "relationshipCode": m.relationship_code,
            "dateOfBirth": m.date_of_birth.isoformat() if m.date_of_birth else None,
            "ageAtInclusion": _age_on(m.date_of_birth, inclusion),
            "eligibilityDecision": qm.eligibility_evaluation.decision if qm.eligibility_evaluation else None,
            "quoteMemberStatus": qm.status,
            "newborn": _is_newborn(m, inclusion, window, categories),
        })
    current_annual = None
    if policy.source_quote.latest_pricing_run_id and policy.source_quote.latest_pricing_run.total_amount is not None:
        current_annual = round_amount(policy.source_quote.latest_pricing_run.total_amount)
    applied_annual = sum(
        (Decimal(str((e.payload_json or {}).get("annualPremium") or "0"))
         for e in policy.endorsements.filter(endorsement_type=EndorsementType.ADD_MEMBER.value)),
        Decimal("0"),
    )
    current_total = (current_annual + applied_annual) if current_annual is not None else None
    return {
        "quoteId": str(quote.id),
        "policy": {
            "id": str(policy.id), "number": policy.policy_number,
            "startDate": policy.start_date.isoformat(), "endDate": policy.end_date.isoformat(),
            "paymentFrequency": frequency,
            "activeMembers": policy.members.filter(status=PolicyMemberStatus.ACTIVE.value,
                                                   exclusion_date__isnull=True).count(),
            "currentAnnualPremium": str(current_total) if current_total is not None else None,
        },
        "inclusionDate": inclusion.isoformat(),
        "currencyCode": run.currency_code,
        "pricingRunId": str(run.id),
        "tariffDate": run.effective_date.isoformat(),
        "annualPremium": str(annual),
        "days": {"remaining": remaining, "basis": basis, "basisCode": config["day_count_basis"],
                 "factor": str(factor.quantize(Decimal("0.000001")))},
        "proRataPremium": str(pro_rata),
        "minimumPremium": str(minimum),
        "minimumApplied": premium > pro_rata,
        "endorsementPremium": str(premium),
        "prepaidPeriodCharge": config["prepaid_period_charge"],
        "fractionation": {"frequency": frequency, "loading": str(loading), "applied": loading > 0,
                          "installments": len(installments)},
        "totalCharged": str(total_charged),
        "installments": installments,
        "newAnnualPremiumReference": str(current_total + annual) if current_total is not None else None,
        "members": members,
        "newbornAutoInclusion": bool(members) and all(m["newborn"] for m in members),
    }


def describe(quote: Quote) -> dict[str, Any]:
    """O cálculo congelado (depois da submissão) ou o atual (antes)."""
    require_endorsement(quote)
    expire_offers()
    quote.refresh_from_db()
    data = quote.endorsement_json or {}
    frozen = data.get("calculation")
    calculation = frozen if frozen and quote.status not in ("DRAFT", "READY") else (
        calculate(quote) if quote.latest_pricing_run_id else None
    )
    return {
        "quoteId": str(quote.id), "status": quote.status, "inclusionDate": data.get("inclusionDate"),
        "policyId": data.get("policyId"), "policyNumber": data.get("policyNumber"),
        "acceptanceDeadline": data.get("acceptanceDeadline"), "clientResponse": data.get("clientResponse"),
        "autoApproved": data.get("autoApproved", False), "appliedEndorsementNo": data.get("appliedEndorsementNo"),
        "calculation": calculation,
    }


# ----------------------------------------------------- submissão e aprovação
def before_submit(quote: Quote) -> None:
    """Chamado por `submit_quote`: valida a data e congela o cálculo."""
    if quote.quote_type != ENDORSEMENT:
        return
    policy = _active_policy(quote.source_policy_id)
    _check_inclusion_date(policy, _inclusion_date(quote))
    calculation = calculate(quote)
    Quote.objects.filter(id=quote.id).update(
        endorsement_json={**(quote.endorsement_json or {}), "calculation": calculation,
                          "submittedCalculationAt": timezone.now().isoformat()},
    )
    quote.refresh_from_db()


def after_submit(quote: Quote, *, correlation_id: str | None) -> Quote:
    """Recém-nascidos dentro da janela: inclusão automática, sem revisão."""
    from apps.quote.application import quote_service

    if quote.quote_type != ENDORSEMENT:
        return quote
    calculation = (quote.endorsement_json or {}).get("calculation") or {}
    if not calculation.get("newbornAutoInclusion"):
        return quote
    now = timezone.now()
    with transaction.atomic():
        updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.IN_REVIEW.value).update(
            status=QuoteStatus.APPROVED.value, approved_by=NEWBORN_APPROVER, approved_at=now,
            row_version=quote.row_version + 1,
        )
        if not updated:
            return quote
        ReviewTask.objects.filter(quote=quote, status__in=(ReviewTaskStatus.OPEN.value, ReviewTaskStatus.IN_PROGRESS.value)).update(
            status=ReviewTaskStatus.DECIDED.value, decided_at=now,
        )
        quote.refresh_from_db()
        quote_service._create_snapshot(quote=quote, snapshot_type="APPROVAL")
        quote_service._record_transition(
            quote, from_status=QuoteStatus.IN_REVIEW.value, to_status=QuoteStatus.APPROVED.value,
            reason_code="NEWBORN_AUTO_INCLUSION", reason_text="Recém-nascido dentro da janela de inclusão automática",
            correlation_id=correlation_id,
        )
        Quote.objects.filter(id=quote.id).update(
            endorsement_json={**(quote.endorsement_json or {}), "autoApproved": True},
        )
        quote.refresh_from_db()
        after_approval(quote)
    _audit.record(action="quote.endorsement_auto_approved", entity_type="Quote", entity_id=str(quote.id),
                  correlation_id=correlation_id, metadata={"reason": "NEWBORN_AUTO_INCLUSION"})
    return quote


def after_approval(quote: Quote) -> None:
    """Aprovado pela subscrição: a proposta segue para o cliente, com prazo."""
    if quote.quote_type != ENDORSEMENT:
        return
    days = int(settings(quote.reference_date).get("acceptance_days") or DEFAULTS["acceptance_days"])
    deadline = _today() + datetime.timedelta(days=days)
    inclusion = _inclusion_date(quote)
    # O cliente tem de responder até à data de inclusão (não há inclusões com data passada).
    deadline = min(deadline, inclusion)
    Quote.objects.filter(id=quote.id).update(
        endorsement_json={**(quote.endorsement_json or {}), "acceptanceDeadline": deadline.isoformat(),
                          "offeredAt": timezone.now().isoformat()},
    )
    quote.refresh_from_db()
    _outbox.append(
        aggregate_type="Quote", aggregate_id=str(quote.id), event_type="ENDORSEMENT.OFFERED", correlation_id=None,
        payload={"quoteId": str(quote.id), "policyId": str(quote.source_policy_id),
                 "acceptanceDeadline": deadline.isoformat()},
    )


# ------------------------------------------------------- resposta do cliente
def expire_offers(today: datetime.date | None = None) -> int:
    """Propostas aprovadas cujo prazo passou ficam EXPIRED (sem efeito)."""
    from apps.quote.application import quote_service

    today = today or _today()
    expired = 0
    for quote in Quote.objects.filter(quote_type=ENDORSEMENT, status=QuoteStatus.APPROVED.value):
        deadline = (quote.endorsement_json or {}).get("acceptanceDeadline")
        if not deadline or datetime.date.fromisoformat(deadline) >= today:
            continue
        updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.APPROVED.value).update(
            status=QuoteStatus.EXPIRED.value, row_version=quote.row_version + 1,
        )
        if not updated:
            continue
        expired += 1
        quote.refresh_from_db()
        quote_service._record_transition(
            quote, from_status=QuoteStatus.APPROVED.value, to_status=QuoteStatus.EXPIRED.value,
            reason_code="ENDORSEMENT_ACCEPTANCE_DEADLINE", reason_text=f"Prazo de aceitação terminou em {deadline}",
        )
        _audit.record(action="quote.endorsement_expired", entity_type="Quote", entity_id=str(quote.id),
                      metadata={"acceptanceDeadline": deadline})
        _outbox.append(aggregate_type="Quote", aggregate_id=str(quote.id), event_type="ENDORSEMENT.EXPIRED",
                       correlation_id=None, payload={"quoteId": str(quote.id), "acceptanceDeadline": deadline})
    return expired


def respond(*, quote: Quote, decision: str, reason: str | None, channel: str, correlation_id: str | None) -> dict[str, Any]:
    """Resposta do cliente (registada pelo GTE ou dada no portal)."""
    require_endorsement(quote)
    if decision not in ("ACCEPT", "REFUSE"):
        raise EndorsementError("decision tem de ser ACCEPT ou REFUSE")
    expire_offers()
    quote.refresh_from_db()
    if quote.status != QuoteStatus.APPROVED.value:
        raise EndorsementStateError(
            f"O endosso está em {quote.status}; o cliente só responde a uma proposta aprovada (APPROVED) dentro do prazo"
        )
    if decision == "REFUSE":
        reason = require_reason(reason)
        Quote.objects.filter(id=quote.id, status=QuoteStatus.APPROVED.value).update(
            status=QuoteStatus.CANCELLED.value, cancellation_reason=f"Recusado pelo cliente: {reason}",
            endorsement_json={**(quote.endorsement_json or {}), "clientResponse": {
                "decision": "REFUSE", "reason": reason, "channel": channel, "at": timezone.now().isoformat(),
                "by": _actor_id()}},
            row_version=quote.row_version + 1,
        )
        _audit.record(action="quote.endorsement_refused", entity_type="Quote", entity_id=str(quote.id),
                      correlation_id=correlation_id, metadata={"reason": reason, "channel": channel})
        quote.refresh_from_db()
        return describe(quote)
    return _apply(quote, channel=channel, correlation_id=correlation_id)


def _apply(quote: Quote, *, channel: str, correlation_id: str | None) -> dict[str, Any]:
    from apps.policy.application.issuance_service import (
        _ELIGIBILITY_TO_POLICY_MEMBER_STATUS,
        _waiting_period_ends,
    )

    inclusion = _inclusion_date(quote)
    if inclusion < _today():
        raise EndorsementStateError(
            "A data de inclusão já passou e não se aceitam inclusões com data passada; crie um novo endosso"
        )
    calculation = (quote.endorsement_json or {}).get("calculation")
    if not calculation:
        raise EndorsementStateError("O endosso não tem cálculo congelado (submeta-o primeiro)")
    tenant_id = CurrentTenantProvider.require().value
    actor_id = _actor_id()
    with transaction.atomic():
        policy = Policy.objects.select_for_update().select_related("source_quote").get(id=quote.source_policy_id)
        if policy.status != PolicyStatus.ACTIVE.value:
            raise EndorsementStateError(f"A apólice {policy.policy_number} já não está ativa ({policy.status})")
        locked = Quote.objects.filter(id=quote.id, status=QuoteStatus.APPROVED.value).update(
            status=QuoteStatus.BOUND.value, row_version=quote.row_version + 1,
        )
        if not locked:
            raise EndorsementStateError("O endosso mudou de estado entretanto; recarregue")
        added = []
        for qm in quote.members.select_related("eligibility_evaluation"):
            evaluation = qm.eligibility_evaluation
            member_status = _ELIGIBILITY_TO_POLICY_MEMBER_STATUS.get(evaluation.decision if evaluation else None)
            if member_status is None:
                continue  # não elegível: não entra
            if PolicyMember.objects.filter(policy=policy, member_id=qm.member_id, exclusion_date__isnull=True).exists():
                raise EndorsementStateError(f"A pessoa {qm.member_id} já está na apólice")
            pending_code = None
            if member_status == PolicyMemberStatus.PENDING.value and evaluation.evidence_json:
                pending_code = evaluation.evidence_json[0].get("code")
            pm = PolicyMember.objects.create(
                tenant_id=tenant_id, policy=policy, member_id=qm.member_id, status=member_status,
                pending_reason_code=pending_code, eligibility_evaluation=evaluation,
                rule_version=evaluation.rule_version if evaluation else None,
                inclusion_date=inclusion if member_status == PolicyMemberStatus.ACTIVE.value else None,
            )
            if member_status == PolicyMemberStatus.ACTIVE.value:
                PolicyMember.objects.filter(id=pm.id).update(
                    waiting_period_ends_json=_waiting_period_ends(policy=policy, policy_member=pm, inclusion_date=inclusion)
                )
            added.append({"memberId": str(qm.member_id), "status": member_status})

        top = policy.installments.aggregate(m=Max("installment_no"))["m"] or 0
        created_installments = []
        for offset, row in enumerate(calculation["installments"], start=1):
            installment = PremiumInstallment.objects.create(
                tenant_id=tenant_id, policy=policy, installment_no=top + offset,
                period_from=datetime.date.fromisoformat(row["periodFrom"]),
                period_to=datetime.date.fromisoformat(row["periodTo"]),
                due_date=datetime.date.fromisoformat(row["dueDate"]),
                amount=Decimal(row["amount"]), currency_code=policy.currency_code or calculation.get("currencyCode") or "AOA",
                status="DUE",
            )
            created_installments.append(installment.installment_no)

        number = (policy.endorsements.aggregate(top=Max("endorsement_number"))["top"] or 0) + 1
        PolicyEndorsement.objects.create(
            tenant_id=tenant_id, policy=policy, endorsement_number=number,
            endorsement_type=EndorsementType.ADD_MEMBER.value, effective_date=inclusion,
            payload_json={
                "quoteId": str(quote.id), "members": added, "annualPremium": calculation["annualPremium"],
                "proRataPremium": calculation["proRataPremium"], "endorsementPremium": calculation["endorsementPremium"],
                "totalCharged": calculation["totalCharged"], "days": calculation["days"],
                "installmentNumbers": created_installments, "channel": channel,
                "autoApproved": (quote.endorsement_json or {}).get("autoApproved", False),
            },
            created_by=actor_id,
        )
        Quote.objects.filter(id=quote.id).update(endorsement_json={
            **(quote.endorsement_json or {}),
            "clientResponse": {"decision": "ACCEPT", "channel": channel, "at": timezone.now().isoformat(), "by": actor_id},
            "appliedEndorsementNo": number,
        })
    _audit.record(
        action="policy.endorsement_applied", entity_type="Policy", entity_id=str(policy.id),
        correlation_id=correlation_id,
        metadata={"quoteId": str(quote.id), "endorsementNo": number, "members": added,
                  "totalCharged": calculation["totalCharged"], "inclusionDate": inclusion.isoformat()},
    )
    _outbox.append(
        aggregate_type="Policy", aggregate_id=str(policy.id), event_type="POLICY.ENDORSED", correlation_id=correlation_id,
        payload={"policyId": str(policy.id), "endorsementNo": number, "type": EndorsementType.ADD_MEMBER.value,
                 "quoteId": str(quote.id), "inclusionDate": inclusion.isoformat()},
    )
    quote.refresh_from_db()
    return describe(quote)


# ------------------------------------------------------------------ listagens
def list_for_policy(policy_id) -> dict[str, Any]:
    policy = Policy.objects.filter(id=policy_id).first()
    if policy is None:
        raise EndorsementNotFoundError(f"A apólice {policy_id} não existe neste tenant")
    expire_offers()
    applied = [
        {"endorsementNo": e.endorsement_number, "type": e.endorsement_type, "effectiveDate": e.effective_date.isoformat(),
         "createdBy": e.created_by, "createdAt": e.created_at.isoformat() if e.created_at else None, "payload": e.payload_json}
        for e in policy.endorsements.order_by("-endorsement_number")
    ]
    quotes = [
        {"quoteId": str(q.id), "quoteNumber": q.quote_number, "status": q.status,
         "inclusionDate": (q.endorsement_json or {}).get("inclusionDate"),
         "acceptanceDeadline": (q.endorsement_json or {}).get("acceptanceDeadline"),
         "totalCharged": ((q.endorsement_json or {}).get("calculation") or {}).get("totalCharged"),
         "createdAt": q.created_at.isoformat() if q.created_at else None}
        for q in Quote.objects.filter(source_policy_id=policy.id, quote_type=ENDORSEMENT).order_by("-created_at")
    ]
    return {"policyId": str(policy.id), "policyNumber": policy.policy_number, "endorsements": applied, "quotes": quotes}


def offers_for_proposers(proposer_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    """Portal do cliente: propostas de endosso à espera de resposta."""
    expire_offers()
    result = []
    for quote in Quote.objects.filter(quote_type=ENDORSEMENT, status=QuoteStatus.APPROVED.value,
                                      proposer_id__in=proposer_ids).order_by("created_at"):
        data = describe(quote)
        result.append(data)
    return result
