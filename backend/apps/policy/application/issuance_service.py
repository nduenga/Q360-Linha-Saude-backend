"""Policy issuance and activation (ROADMAP_APOLICES.md Fase 3).

PO-APO-1 (2026-09-26): a Quote becomes a contract only when the tomador
signs — never on approval alone. `issue_policy()` is that moment: it
requires an already-`APPROVED` Quote and a real signature, and creates
the Policy in `PENDING_FIRST_PREMIUM` — no coverage exists yet (Decreto
n.º 2/02 art. 17.º: the premium's first fraction is due at the contract's
celebration). `register_first_premium_payment()` is the second, separate
moment (art. 17.º again) that actually starts the risk — `PENDING_FIRST_
PREMIUM` -> `ACTIVE`, with `start_date` computed as the day *after*
whichever of signature/payment happened last (never the same day — see
ROADMAP_APOLICES.md "Início do risco", fraud-proofing against a claim
from the morning of the signing/payment day itself).

Every quantity a business decision (payment deadlines, new-business
tolerance days) is intentionally NOT hardcoded here — Fase 7 (falta de
pagamento) is where those get a real, configurable answer.
"""
from __future__ import annotations

import calendar
import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils.timezone import now as timezone_now

from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.domain.shape import flatten
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.client.domain.enums import ProposerType
from apps.eligibility.domain.enums import EligibilityDecision
from apps.eligibility.domain.evaluation import AngolaEvidence
from apps.eligibility.infrastructure.rule_repository import parse_config
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.infrastructure.models import PricingComponent
from apps.policy.domain.enums import PolicyMemberStatus, PolicyStatus, PolicyType, SignatureMethod
from apps.policy.domain.errors import (
    DuplicatePolicyError,
    InvalidStartDateError,
    PolicyStateError,
    ReferencedEntityNotFoundError,
    RowVersionMismatchError,
)
from apps.policy.infrastructure.models import Policy, PolicyMember, PolicySignature, PremiumInstallment
from apps.quote.application.numbering_service import next_continuous_value
from apps.quote.domain.enums import QuoteMemberStatus, QuoteStatus
from apps.quote.infrastructure.models import Quote, QuoteSnapshot

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()

_INSTALLMENT_COUNT = {"ANUAL": 1, "SEMESTRAL": 2, "TRIMESTRAL": 4, "MENSAL": 12}

# PO-APO-2: a member's own subscription outcome never blocks the rest of
# the policy — it only ever affects this member's own row.
_ELIGIBILITY_TO_POLICY_MEMBER_STATUS = {
    EligibilityDecision.ELIGIBLE.value: PolicyMemberStatus.ACTIVE.value,
    EligibilityDecision.WARNING.value: PolicyMemberStatus.ACTIVE.value,
    EligibilityDecision.ELIGIBLE_WITH_LOADING.value: PolicyMemberStatus.ACTIVE.value,
    EligibilityDecision.PENDING_DOCUMENT.value: PolicyMemberStatus.PENDING.value,
    EligibilityDecision.PENDING_MEDICAL_BOARD.value: PolicyMemberStatus.PENDING.value,
    EligibilityDecision.REFERRAL.value: PolicyMemberStatus.PENDING.value,
    # HARD_STOP/CONFIG_ERROR are never copied at all (see issue_policy).
}


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fractionation_loading(quote: Quote, payment_frequency: str) -> Decimal:
    """Encargo de fracionamento (Dashboard_Premissas!D61:D64 / Calculador!E91:E94).

    Decisão A8 (2026-10-14): aplica-se a todas as apólices.
      1. `pricing.fractionation` publicada e vigente na data de efeito da
         cotação (editável pela interface; a do produto prevalece sobre a geral);
      2. senão, a tabela do modelo atuarial registado no cálculo do prémio
         (a versão usada nesse cálculo, não a publicada hoje);
      3. senão, sem encargo (partes iguais)."""
    config = BusinessConfigurationResolver.get(
        "pricing.fractionation", effective_date=quote.reference_date, product_id=quote.plan.product_id)
    if config is not None:
        rows = flatten("pricing.fractionation", config.value_json).get("installments") or []
        return _loading_for(rows, payment_frequency)
    run = quote.latest_pricing_run
    used = (run.business_configuration_snapshot_json or {}).get("pricing.actuarial_model") if run else None
    if not used:
        return Decimal("0")
    model = BusinessConfiguration.objects.filter(id=used.get("configurationId")).values_list("value_json", flat=True).first()
    return _loading_for(((model or {}).get("assumptions") or {}).get("payment_installments") or [], payment_frequency)


def _loading_for(rows: list, payment_frequency: str) -> Decimal:
    row = next((r for r in rows if str(r.get("frequency", "")).strip().upper() == payment_frequency), None)
    return Decimal(str(row["loading"])) if row and row.get("loading") not in (None, "") else Decimal("0")


def product_formula_installment(quote: Quote, payment_frequency: str) -> Decimal | None:
    """Prestação calculada por uma fórmula de fracionamento do produto
    (ex.: «Prémio semestral = Prémio anual ÷ 2»), no cálculo da cotação."""
    run = quote.latest_pricing_run
    if run is None:
        return None
    component = PricingComponent.objects.filter(pricing_run=run, component_code="PRODUCT_FORMULAS").first()
    value = ((component.metadata_json or {}).get("installments") or {}).get(payment_frequency) if component else None
    return Decimal(str(value)) if value not in (None, "") else None


def installment_amount(quote: Quote, total_amount: Decimal, payment_frequency: str) -> Decimal:
    from_formula = product_formula_installment(quote, payment_frequency)
    if from_formula is not None:
        return _round2(from_formula)
    count = _INSTALLMENT_COUNT[payment_frequency]
    return _round2(total_amount * (Decimal("1") + fractionation_loading(quote, payment_frequency)) / count)


def issue_policy(
    *,
    quote: Quote,
    signatory_name: str,
    signatory_document_type: str,
    signatory_document_number: str,
    signatory_capacity: str,
    signature_method: str,
    signed_at: datetime.datetime,
    term_months: int,
    payment_frequency: str,
    requested_start_date: datetime.date | None,
    row_version: int,
    correlation_id: str | None,
) -> Policy:
    if quote.quote_type == "ENDORSEMENT":
        raise PolicyStateError(
            f"A cotação {quote.id} é um endosso de inclusão: aplica-se à apólice com a aceitação do cliente "
            "(POST /quotes/{id}/endorsement/response), não origina uma apólice nova"
        )
    if quote.status != QuoteStatus.APPROVED.value:
        raise PolicyStateError(f"A cotação {quote.id} está em {quote.status}; só uma cotação APROVADA (APPROVED) pode ser assinada")
    if quote.valid_until is not None and signed_at.date() > quote.valid_until:
        raise PolicyStateError(f"A cotação {quote.id} expirou em {quote.valid_until}; é necessária uma nova cotação")

    if requested_start_date is not None:
        # OD-APO-003: never on/before the signature date itself
        # (fraud-proofing — see module docstring). The quote has no
        # effective date any more (2026-10-15): the start of cover is
        # chosen here, and the signature is always after the quote's
        # creation, so this also keeps it after the pricing reference date.
        # The other half of the rule (never before the *payment* date) can
        # only be enforced once payment happens — see
        # register_first_premium_payment().
        if requested_start_date <= signed_at.date():
            raise InvalidStartDateError(
                f"A data de início pedida ({requested_start_date}) tem de ser posterior à data de assinatura ({signed_at.date()})"
            )

    snapshot = (
        QuoteSnapshot.objects.filter(quote=quote, snapshot_type="APPROVAL").order_by("-snapshot_no").first()
    )
    if snapshot is None:
        raise PolicyStateError(f"A cotação {quote.id} não tem registo de aprovação (snapshot); não é possível determinar os termos contratados")

    if Policy.objects.filter(source_quote=quote).exists():
        raise DuplicatePolicyError(f"A cotação {quote.id} já originou uma apólice")

    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"

    policy_type = (
        PolicyType.GROUP.value
        if quote.proposer.proposer_type == ProposerType.ORGANISATION.value
        else PolicyType.INDIVIDUAL.value
    )
    policy_number = next_continuous_value(sequence_code="POLICY_NUMBER", prefix="APO-")

    total_amount = (
        quote.latest_pricing_run.total_amount
        if quote.latest_pricing_run and quote.latest_pricing_run.total_amount is not None
        else None
    )

    try:
        with transaction.atomic():
            updated = Quote.objects.filter(
                id=quote.id, status=QuoteStatus.APPROVED.value, row_version=row_version
            ).update(status=QuoteStatus.BOUND.value, row_version=row_version + 1)
            if updated == 0:
                quote.refresh_from_db()
                if quote.status != QuoteStatus.APPROVED.value:
                    raise PolicyStateError(f"A cotação {quote.id} está em {quote.status}; só uma cotação APROVADA (APPROVED) pode ser assinada")
                raise RowVersionMismatchError(
                    f"A versão da cotação {quote.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
                )

            policy = Policy.objects.create(
                tenant_id=tenant_id.value,
                policy_number=policy_number,
                source_quote=quote,
                contracted_terms_snapshot=snapshot,
                proposer=quote.proposer,
                plan=quote.plan,
                policy_type=policy_type,
                term_months=term_months,
                requested_start_date=requested_start_date,
                status=PolicyStatus.PENDING_FIRST_PREMIUM.value,
                payment_frequency=payment_frequency,
                currency_code=quote.currency_code,
                issued_by=actor_id,
            )
            PolicySignature.objects.create(
                tenant_id=tenant_id.value,
                policy=policy,
                signatory_name=signatory_name,
                signatory_document_type=signatory_document_type,
                signatory_document_number=signatory_document_number,
                signatory_capacity=signatory_capacity,
                signature_method=signature_method,
                signed_at=signed_at,
                registered_by=actor_id,
            )

            for quote_member in quote.members.select_related("eligibility_evaluation").all():
                evaluation = quote_member.eligibility_evaluation
                decision = evaluation.decision if evaluation else None
                member_status = _ELIGIBILITY_TO_POLICY_MEMBER_STATUS.get(decision)
                if member_status is None:
                    # HARD_STOP/CONFIG_ERROR (QuoteMemberStatus.EXCLUDED) —
                    # never copied onto the Policy at all.
                    continue
                pending_reason_code = None
                if member_status == PolicyMemberStatus.PENDING.value and evaluation.evidence_json:
                    pending_reason_code = evaluation.evidence_json[0].get("code")
                PolicyMember.objects.create(
                    tenant_id=tenant_id.value,
                    policy=policy,
                    member_id=quote_member.member_id,
                    status=member_status,
                    pending_reason_code=pending_reason_code,
                    eligibility_evaluation=evaluation,
                    rule_version=evaluation.rule_version if evaluation else None,
                )

            if total_amount is not None:
                first_amount = installment_amount(quote, total_amount, payment_frequency)
                today = timezone_now().date()
                PremiumInstallment.objects.create(
                    tenant_id=tenant_id.value,
                    policy=policy,
                    installment_no=1,
                    # Provisional bounds — recalculated against the real
                    # start_date once activation determines it (see
                    # register_first_premium_payment).
                    period_from=today,
                    period_to=today,
                    due_date=today,
                    amount=first_amount,
                    currency_code=quote.currency_code or "AOA",
                    status="DUE",
                )

    except (PolicyStateError, RowVersionMismatchError, DuplicatePolicyError):
        raise

    close_source_policy_if_due(policy=policy, moment="ISSUANCE")
    _audit.record(
        action="policy.issued",
        entity_type="Policy",
        entity_id=str(policy.id),
        correlation_id=correlation_id,
        metadata={"quoteId": str(quote.id), "policyNumber": policy.policy_number},
    )
    _outbox.append(
        aggregate_type="Policy",
        aggregate_id=str(policy.id),
        event_type="POLICY.ISSUED",
        correlation_id=correlation_id,
        payload={
            "policyId": str(policy.id),
            "policyNumber": policy.policy_number,
            "quoteId": str(quote.id),
            "proposerId": str(quote.proposer_id),
            "status": policy.status,
        },
    )
    return policy


# Quando a apólice de origem de uma renovação passa a RENEWED. A renovação é
# negociada numa cotação (RENEWAL); só quando essa cotação se converte em
# apólice é que a anterior pode ser encerrada. Recomendado (por omissão):
# na ativação (1.º prémio pago), porque só então a continuidade da cobertura
# está garantida; configurável em `renewal.deadlines.previous_policy_close`.
CLOSE_ON_ISSUANCE = "ON_RENEWAL_ISSUANCE"
CLOSE_ON_ACTIVATION = "ON_RENEWAL_ACTIVATION"
CLOSE_ON_EFFECTIVE_DATE = "ON_EFFECTIVE_DATE"
CLOSE_MANUAL = "MANUAL"
DEFAULT_CLOSE_MODE = CLOSE_ON_ACTIVATION
_RENEWABLE_SOURCE_STATUSES = (PolicyStatus.ACTIVE.value, PolicyStatus.EXPIRED.value)


def _plan_settings(policy: Policy) -> dict:
    return ((policy.contracted_terms_snapshot.snapshot_json or {}).get("plan") or {}).get("settings") or {}


def close_source_policy_if_due(*, policy: Policy, moment: str, today: datetime.date | None = None) -> Policy | None:
    """Marca a apólice de origem como RENEWED quando `moment` coincide com a
    regra configurada. `moment` ∈ ISSUANCE, ACTIVATION, EFFECTIVE_DATE."""
    quote = policy.source_quote
    if quote.quote_type != "RENEWAL" or not quote.source_policy_id:
        return None
    mode = (_plan_settings(policy).get("renewalDeadlines") or {}).get("previous_policy_close") or DEFAULT_CLOSE_MODE
    today = today or datetime.date.today()
    due = (
        (mode == CLOSE_ON_ISSUANCE and moment == "ISSUANCE")
        or (mode == CLOSE_ON_ACTIVATION and moment == "ACTIVATION")
        or (
            mode == CLOSE_ON_EFFECTIVE_DATE
            and moment in ("ACTIVATION", "EFFECTIVE_DATE")
            and policy.status == PolicyStatus.ACTIVE.value
            and policy.start_date is not None
            and policy.start_date <= today
        )
    )
    if not due:
        return None
    source = Policy.objects.filter(id=quote.source_policy_id).first()
    if source is None or source.status not in _RENEWABLE_SOURCE_STATUSES:
        return None
    Policy.objects.filter(id=source.id, status=source.status).update(
        status=PolicyStatus.RENEWED.value, row_version=source.row_version + 1
    )
    source.refresh_from_db()
    _audit.record(
        action="policy.renewed",
        entity_type="Policy",
        entity_id=str(source.id),
        metadata={"renewedByPolicyId": str(policy.id), "renewedByPolicyNumber": policy.policy_number, "rule": mode},
    )
    _outbox.append(
        aggregate_type="Policy",
        aggregate_id=str(source.id),
        event_type="POLICY.RENEWED",
        payload={"policyId": str(source.id), "policyNumber": source.policy_number, "renewedByPolicyId": str(policy.id)},
    )
    return source


def close_renewed_policies(*, today: datetime.date | None = None) -> int:
    """Para a regra ON_EFFECTIVE_DATE: encerra as apólices de origem cuja
    renovação já está em vigor (corre diariamente)."""
    closed = 0
    for policy in Policy.objects.filter(status=PolicyStatus.ACTIVE.value, source_quote__quote_type="RENEWAL").select_related(
        "source_quote", "contracted_terms_snapshot"
    ):
        if close_source_policy_if_due(policy=policy, moment="EFFECTIVE_DATE", today=today):
            closed += 1
    return closed


def _plan_benefit_codes(policy: Policy) -> list[str]:
    """Reads the frozen plan content from the snapshot — never the live
    Plan (DECISIONS_TAKEN.md#S09-POLICY-001 Fase 1: what was contracted
    must never drift with a later Plan edit)."""
    plan_json = (policy.contracted_terms_snapshot.snapshot_json or {}).get("plan") or {}
    return [b["code"] for b in plan_json.get("benefits", []) if b.get("code") and b.get("contracted", True)]


def _coverage_waiting_days(policy: Policy) -> dict[str, int]:
    """Waiting days configured on each contracted coverage of the plan (PDF:
    carência por cobertura, individual vs grupo). Frozen in the snapshot.
    A value of 0 means "no waiting period" and overrides the rule default."""
    plan_json = (policy.contracted_terms_snapshot.snapshot_json or {}).get("plan") or {}
    key = "group" if (plan_json.get("settings") or {}).get("segment") == "GROUP" else "individual"
    out: dict[str, int] = {}
    for benefit in plan_json.get("benefits", []):
        if not benefit.get("contracted", True):
            continue
        days = ((benefit.get("configurationJson") or {}).get("waitingDays") or {}).get(key)
        # 0 é uma escolha explícita («sem carência», p. ex. urgências) e tem de
        # prevalecer sobre a carência genérica da regra de elegibilidade.
        if isinstance(days, int) and not isinstance(days, bool) and days >= 0:
            out[benefit["code"]] = days
    return out


def _waiting_period_ends(*, policy: Policy, policy_member: PolicyMember, inclusion_date: datetime.date) -> dict:
    config = parse_config(policy_member.rule_version) if policy_member.rule_version is not None else None
    wp = config.waiting_period if config is not None else None

    evaluation = policy_member.eligibility_evaluation
    context = (evaluation.input_snapshot_json.get("context") if evaluation else None) or {}
    evidence = AngolaEvidence.from_dict(context.get("angola"))
    waived = (
        wp is not None
        and wp.waived_on_verified_portability
        and bool(evidence.previous_policy_number)
        and evidence.previous_policy_continuous
    )
    if waived:
        return {}

    # Renovação: quem transita da apólice anterior mantém as carências já
    # cumpridas, se o negócio o definiu (`renewal.rules`).
    quote = policy.source_quote
    if (
        quote.quote_type == "RENEWAL"
        and (_plan_settings(policy).get("renewal") or {}).get("continuityWithoutNewWaiting") is True
        and str(policy_member.member_id) in ((quote.renewal_json or {}).get("carriedMembers") or [])
    ):
        return {}

    coverage_days = _coverage_waiting_days(policy)
    ends: dict[str, str] = {}
    for code in _plan_benefit_codes(policy):
        # The coverage's own waiting period (plan configuration) wins; the
        # eligibility rule's generic one is the fallback.
        days = coverage_days.get(code)
        if days is None and wp is not None:
            days = wp.default_days_by_benefit_category.get(code, wp.default_days)
        if days and days > 0:
            ends[code] = (inclusion_date + datetime.timedelta(days=days)).isoformat()
    return ends


_POLICY_STATUS_TEXT = {
    "ACTIVE": "ativa", "CANCELLED": "cancelada", "EXPIRED": "expirada", "RENEWED": "renovada",
    "SUSPENDED": "suspensa", "PENDING_FIRST_PREMIUM": "a aguardar o 1.º prémio",
}


def _not_pending_message(policy: Policy) -> str:
    """Mensagem para quem tenta registar o 1.º prémio de uma apólice que já não o espera."""
    number = policy.policy_number or "esta apólice"
    if PremiumInstallment.objects.filter(policy=policy, installment_no=1, status="PAID").exists():
        return f"A 1.ª prestação da apólice {number} já está paga."
    state = _POLICY_STATUS_TEXT.get(policy.status, policy.status)
    return f"A apólice {number} está {state}; só se regista o 1.º prémio de uma apólice a aguardar esse pagamento."


def register_first_premium_payment(
    *,
    policy: Policy,
    paid_at: datetime.datetime,
    payment_reference: str | None,
    payment_method: str | None,
    row_version: int,
    correlation_id: str | None,
) -> Policy:
    if policy.status != PolicyStatus.PENDING_FIRST_PREMIUM.value:
        raise PolicyStateError(_not_pending_message(policy))

    installment = PremiumInstallment.objects.filter(policy=policy, installment_no=1, status="DUE").first()
    if installment is None:
        raise ReferencedEntityNotFoundError(f"A apólice {policy.id} não tem a 1.ª prestação por pagar")

    signature = PolicySignature.objects.filter(policy=policy).first()
    if signature is None:
        raise PolicyStateError(f"A apólice {policy.id} não tem assinatura registada")

    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"

    default_start = max(signature.signed_at.date(), paid_at.date()) + datetime.timedelta(days=1)
    start_date = max(default_start, policy.requested_start_date) if policy.requested_start_date else default_start
    end_date = _add_months(start_date, policy.term_months) - datetime.timedelta(days=1)

    with transaction.atomic():
        updated = Policy.objects.filter(
            id=policy.id, status=PolicyStatus.PENDING_FIRST_PREMIUM.value, row_version=row_version
        ).update(
            status=PolicyStatus.ACTIVE.value,
            start_date=start_date,
            end_date=end_date,
            row_version=row_version + 1,
        )
        if updated == 0:
            policy.refresh_from_db()
            if policy.status != PolicyStatus.PENDING_FIRST_PREMIUM.value:
                raise PolicyStateError(_not_pending_message(policy))
            raise RowVersionMismatchError(
                f"A versão da apólice {policy.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
            )

        PremiumInstallment.objects.filter(id=installment.id).update(
            status="PAID",
            paid_at=paid_at,
            payment_reference=payment_reference,
            payment_method=payment_method,
            registered_by=actor_id,
            period_from=start_date,
            period_to=_period_end_for(start_date, policy.payment_frequency),
            due_date=start_date,
        )
        _create_remaining_installments(policy=policy, start_date=start_date, tenant_id=tenant_id.value)

        for policy_member in PolicyMember.objects.filter(policy_id=policy.id, status=PolicyMemberStatus.ACTIVE.value):
            waiting_period_ends = _waiting_period_ends(policy=policy, policy_member=policy_member, inclusion_date=start_date)
            PolicyMember.objects.filter(id=policy_member.id).update(
                inclusion_date=start_date,
                waiting_period_ends_json=waiting_period_ends,
                row_version=policy_member.row_version + 1,
            )

    policy.refresh_from_db()
    close_source_policy_if_due(policy=policy, moment="ACTIVATION")
    _audit.record(
        action="policy.activated",
        entity_type="Policy",
        entity_id=str(policy.id),
        correlation_id=correlation_id,
        metadata={"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
    )
    _outbox.append(
        aggregate_type="Policy",
        aggregate_id=str(policy.id),
        event_type="POLICY.ACTIVATED",
        correlation_id=correlation_id,
        payload={
            "policyId": str(policy.id),
            "policyNumber": policy.policy_number,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "status": policy.status,
        },
    )
    return policy


def _add_months(date_value: datetime.date, months: int) -> datetime.date:
    month_index = date_value.month - 1 + months
    year = date_value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date_value.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _period_end_for(start_date: datetime.date, payment_frequency: str) -> datetime.date:
    months_per_installment = {"ANUAL": 12, "SEMESTRAL": 6, "TRIMESTRAL": 3, "MENSAL": 1}[payment_frequency]
    return _add_months(start_date, months_per_installment) - datetime.timedelta(days=1)


def _create_remaining_installments(*, policy: Policy, start_date: datetime.date, tenant_id: uuid.UUID) -> None:
    count = _INSTALLMENT_COUNT[policy.payment_frequency]
    if count <= 1 or policy.currency_code is None:
        return
    months_per_installment = {"ANUAL": 12, "SEMESTRAL": 6, "TRIMESTRAL": 3, "MENSAL": 1}[policy.payment_frequency]
    total_amount = PremiumInstallment.objects.filter(policy=policy, installment_no=1).first()
    if total_amount is None:
        return
    per_installment_amount = total_amount.amount
    for index in range(2, count + 1):
        period_from = _add_months(start_date, months_per_installment * (index - 1))
        period_to = _add_months(period_from, months_per_installment) - datetime.timedelta(days=1)
        PremiumInstallment.objects.create(
            tenant_id=tenant_id,
            policy=policy,
            installment_no=index,
            period_from=period_from,
            period_to=period_to,
            due_date=period_from,
            amount=per_installment_amount,
            currency_code=policy.currency_code,
            status="DUE",
        )


def effective_installment_status(installment: PremiumInstallment, today: datetime.date | None = None) -> str:
    """`DUE` com vencimento já passado conta como `OVERDUE` (nada marca o atraso
    na base de dados; deduz-se da data)."""
    today = today or timezone_now().date()
    if installment.status == "DUE" and installment.due_date < today:
        return "OVERDUE"
    return installment.status


def register_installment_payment(
    *,
    policy: Policy,
    installment_no: int,
    paid_at: datetime.datetime,
    payment_reference: str | None,
    payment_method: str | None,
    correlation_id: str | None,
) -> PremiumInstallment:
    """Regista o pagamento de uma prestação **posterior à 1.ª** de uma apólice em
    vigor. As prestações pagam-se por ordem: a anterior tem de estar paga."""
    if installment_no < 2:
        raise ReferencedEntityNotFoundError("A 1.ª prestação regista-se com o fluxo de ativação da apólice")
    if policy.status != PolicyStatus.ACTIVE.value:
        raise PolicyStateError(
            f"A apólice {policy.policy_number} está em {policy.status}; só se registam pagamentos em apólices ativas (ACTIVE)"
        )
    if paid_at.date() > timezone_now().date():
        raise InvalidStartDateError("A data de pagamento não pode estar no futuro")

    installment = PremiumInstallment.objects.filter(policy=policy, installment_no=installment_no).exclude(status="VOID").first()
    if installment is None:
        raise ReferencedEntityNotFoundError(f"A apólice {policy.policy_number} não tem a prestação {installment_no}")
    if installment.status == "PAID":
        raise PolicyStateError(f"A prestação {installment_no} da apólice {policy.policy_number} já está paga")
    unpaid_before = (
        PremiumInstallment.objects.filter(policy=policy, installment_no__lt=installment_no)
        .exclude(status__in=("PAID", "VOID"))
        .order_by("installment_no")
        .first()
    )
    if unpaid_before is not None:
        raise PolicyStateError(f"Registe primeiro o pagamento da prestação {unpaid_before.installment_no}")

    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    with transaction.atomic():
        updated = PremiumInstallment.objects.filter(id=installment.id).exclude(status="PAID").update(
            status="PAID",
            paid_at=paid_at,
            payment_reference=payment_reference,
            payment_method=payment_method,
            registered_by=actor_id,
        )
        if updated == 0:
            raise PolicyStateError(f"A prestação {installment_no} da apólice {policy.policy_number} já está paga")
    installment.refresh_from_db()
    _audit.record(
        action="policy.installment_paid",
        entity_type="Policy",
        entity_id=str(policy.id),
        correlation_id=correlation_id,
        metadata={"installmentNo": installment_no, "paymentReference": payment_reference},
    )
    _outbox.append(
        aggregate_type="Policy",
        aggregate_id=str(policy.id),
        event_type="POLICY.INSTALLMENT.PAID",
        correlation_id=correlation_id,
        payload={"policyId": str(policy.id), "policyNumber": policy.policy_number, "installmentNo": installment_no},
    )
    return installment
