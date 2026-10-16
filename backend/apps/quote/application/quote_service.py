"""Quote orchestration (Q360-S6-01..04): create, population, deterministic
pricing + immutable snapshot, and the DRAFT<->READY side effects ART-009's
"Quote Machine" sheet assigns to QT-001/QT-002 (there is no separate manual
"mark ready" command in ART-006 — becoming READY is an automatic side
effect of a successful `priceQuote` whose population has no HARD_STOP/
CONFIG_ERROR eligibility member; any material edit — member added/removed
— demotes back to DRAFT and invalidates the pricing
reference, per QT-002's "Atomic Side Effects").

OPEN DECISION — see DECISIONS_TAKEN.md#S06-QUOTE-001 for the judgment
calls this module makes (member status mapping, which members are priced,
default validity days, quote numbering).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.timezone import localdate as timezone_localdate
from django.utils.timezone import now as timezone_now

from apps.client.application.member_service import create_member
from apps.client.application.proposer_service import create_proposer
from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.eligibility.domain.enums import EligibilityDecision
from apps.foundation.application.audit_service import AuditService
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.application.auto_resolve import resolve_default_parameter_set_code, resolve_default_rating_table_code
from apps.pricing.application.pricing_engine import calculate_pricing
from apps.business_config.application.overlays import effective_plan_settings, plan_availability
from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.pricing.domain.age_band import compute_age_band
from apps.product.domain.enums import PlanStatus
from apps.product.infrastructure.models import Plan, PlanBenefit
from apps.quote.application.numbering_service import next_continuous_value
from apps.quote.domain.enums import (
    QuoteDecisionType,
    QuoteMemberStatus,
    QuoteSnapshotType,
    QuoteStatus,
    ReviewTaskStatus,
)
from apps.quote.domain.errors import (
    DuplicateMemberError,
    QuoteDeletionBlockedError,
    QuoteStateError,
    ReferencedEntityNotFoundError,
    RowVersionMismatchError,
    SegregationOfDutiesError,
)
from apps.quote.infrastructure.models import (
    AuthorityPolicy,
    Quote,
    QuoteAdjustment,
    QuoteDecision,
    QuoteMember,
    QuoteSnapshot,
    QuoteStateHistory,
    ReviewTask,
)

from apps.client.domain.enums import MemberStatus

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()

_ELIGIBILITY_TO_MEMBER_STATUS = {
    EligibilityDecision.ELIGIBLE.value: QuoteMemberStatus.INCLUDED.value,
    # Angola eligibility has three non-blocking outcomes in addition to
    # the original ART-008 vocabulary.  A loading remains priceable, while
    # documentary/medical cases require an underwriter's review before
    # they can become active on the issued policy.
    EligibilityDecision.ELIGIBLE_WITH_LOADING.value: QuoteMemberStatus.INCLUDED.value,
    EligibilityDecision.PENDING_DOCUMENT.value: QuoteMemberStatus.REFERRAL.value,
    EligibilityDecision.PENDING_MEDICAL_BOARD.value: QuoteMemberStatus.REFERRAL.value,
    EligibilityDecision.WARNING.value: QuoteMemberStatus.INCLUDED.value,
    EligibilityDecision.REFERRAL.value: QuoteMemberStatus.REFERRAL.value,
    EligibilityDecision.HARD_STOP.value: QuoteMemberStatus.EXCLUDED.value,
    EligibilityDecision.CONFIG_ERROR.value: QuoteMemberStatus.EXCLUDED.value,
}

# Members actually submitted to the pricing engine. EXCLUDED (HARD_STOP/
# CONFIG_ERROR at add-time) never enter a price; REFERRAL members are
# still priced provisionally (manual underwriting decides inclusion later,
# see DECISIONS_TAKEN.md#S06-QUOTE-001).
_PRICEABLE_MEMBER_STATUSES = [QuoteMemberStatus.INCLUDED.value, QuoteMemberStatus.REFERRAL.value]


def _plan_content_snapshot(plan: Plan, selection: dict | None = None, effective_date: datetime.date | None = None) -> dict:
    """DECISIONS_TAKEN.md#S09-POLICY-001 (ROADMAP_APOLICES.md Fase 1,
    pré-requisito de PO-APO-6): with ProductVersion retired, a Plan is no
    longer immutable once "published" — it can be edited at any time
    (apps.product.application.product_service.update_plan/
    add_plan_benefit/remove_plan_benefit). Every PRICING/SUBMISSION/
    APPROVAL snapshot therefore captures the Plan's full content (not just
    its id), so what a Quote actually contracted stays frozen even if the
    live Plan changes or is later made INACTIVE — the same historical-
    correctness guarantee OD-ANGOLA-004 gave via version immutability
    before this change, now given by the snapshot itself.

    PDF "Coberturas e Capitais": a plan *offers* optional ("O") coverages
    but the customer only *has* the ones chosen. Each benefit therefore
    carries `contracted` (included, or an optional one the quote selected)
    and its **effective** configuration (capitals/participation/waiting days
    after any "e se" override) — policy coverage checks, waiting periods and
    the customer portal read `contracted`, never the bare list of what the
    plan merely offers."""
    from apps.pricing.application.plan_dimensions import resolve_plan_pricing_context

    plan_benefits = {pb.benefit.code: pb for pb in PlanBenefit.objects.filter(plan=plan).select_related("benefit")}
    try:
        context = resolve_plan_pricing_context(plan=plan, selection=selection or {}, effective_date=effective_date)
        rows = [
            (c["code"], c["contracted"], c["inclusion"], c["configuration"]) for c in context.coverages
        ]
        normalised_selection = context.selection
    except DomainProblem:
        rows = [
            (code, (pb.configuration_json or {}).get("inclusion", "INCLUDED") == "INCLUDED", (pb.configuration_json or {}).get("inclusion", "INCLUDED"), pb.configuration_json)
            for code, pb in plan_benefits.items()
        ]
        normalised_selection = selection or {}
    benefits = [
        {
            "benefitId": str(plan_benefits[code].benefit_id),
            "code": code,
            "name": plan_benefits[code].benefit.name,
            "category": plan_benefits[code].benefit.benefit_type,
            "contracted": contracted,
            "inclusion": inclusion,
            "configurationJson": configuration,
        }
        for code, contracted, inclusion, configuration in sorted(rows)
    ]
    return {
        "productId": str(plan.product_id),
        "planId": str(plan.id),
        "planCode": plan.code,
        "planName": plan.name,
        "planStatus": plan.status,
        "settings": effective_plan_settings(plan, effective_date),
        "selection": normalised_selection,
        "benefits": benefits,
    }


def _default_valid_until(start: datetime.date) -> datetime.date:
    """Validade da cotação: `start` (o dia de criação, ou o de reabertura)
    mais `quote.validity_days` dias."""
    # OPEN DECISION: no approved document fixes the default quote validity
    # period. Configurable via QUOTE_DEFAULT_VALIDITY_DAYS (settings/env),
    # never hardcoded in business logic — see DECISIONS_TAKEN.md#S06-QUOTE-001.
    # R7: the GTE can change it without a deploy (system parameter
    # `quote.validity_days`); until they do, the env setting still rules.
    from apps.foundation.application import system_parameter_service

    days = system_parameter_service.get_stored_value("quote.validity_days")
    if days is None:
        days = getattr(settings, "QUOTE_DEFAULT_VALIDITY_DAYS", 30)
    return start + datetime.timedelta(days=days)


def _record_transition(
    quote: Quote, *, from_status: str | None, to_status: str, reason_code: str | None = None,
    reason_text: str | None = None, correlation_id: str | None = None,
) -> None:
    actor = CurrentActorProvider.get()
    QuoteStateHistory.objects.create(
        tenant_id=quote.tenant_id,
        quote=quote,
        from_status=from_status,
        to_status=to_status,
        reason_code=reason_code,
        reason_text=reason_text,
        changed_by=actor.actor_id if actor else "unknown",
        correlation_id=correlation_id,
    )


def _as_date(value: Any) -> datetime.date | None:
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    return value


def create_quote(
    *,
    proposer_id: uuid.UUID | None = None,
    plan_id: uuid.UUID,
    # Atalho para o formulário "nova cotação" que ainda não tem um Proposer
    # persistido. Passar `proposerInput` cria o Proposer atomáticamente e,
    # opcionalmente, passar `titularMemberInput` cria o membro titular (TITULAR)
    # e junta-o à cotação no mesmo passo — tudo transacional: se a cotação
    # falhar, nada fica para trás e nenhuma pessoa/proponente órfão é criada.
    proposer_input: dict[str, Any] | None = None,
    titular_member_input: dict[str, Any] | None = None,
) -> Quote:
    tenant_id = CurrentTenantProvider.require()
    actor = CurrentActorProvider.get()

    created_proposer: Proposer | None = None
    created_member: InsuredMember | None = None
    try:
        with transaction.atomic():
            if proposer_id is None and proposer_input is None:
                raise ReferencedEntityNotFoundError(
                    "Um dos campos 'proposerId' ou 'proposerInput' deve ser fornecido."
                )

            if proposer_input is not None:
                if proposer_id is not None:
                    raise ReferencedEntityNotFoundError(
                        "Envie 'proposerId' OU 'proposerInput' (não ambos) para criar uma cotação."
                    )
                created_proposer = create_proposer(
                    proposer_type=(proposer_input.get("proposerType") or "INDIVIDUAL"),
                    display_name=proposer_input["displayName"],
                    external_reference=(
                        proposer_input.get("externalReference")
                        if "externalReference" in proposer_input
                        else None
                    ),
                    nif=proposer_input["nif"],
                    registration_number=proposer_input["registrationNumber"],
                    email=proposer_input.get("email") or "",
                    phone=proposer_input.get("phone") or "",
                    attributes=(
                        proposer_input.get("attributes") if "attributes" in proposer_input else None
                    ),
                    # Individual: obrigatória (o titular é o próprio proponente).
                    date_of_birth=_as_date(
                        proposer_input.get("dateOfBirth")
                        or (titular_member_input or {}).get("dateOfBirth")
                    ),
                    require_birth_date=True,
                )
                proposer_id = created_proposer.id
                if titular_member_input is not None:
                    # O titular criado no mesmo passo é sempre relação TITULAR
                    # com o próprio Proposer (a menos que o formulário indique
                    # outro, mas por default é TITULAR)
                    relationship_code = (titular_member_input.get("relationshipCode") or "TITULAR").upper()
                    first_name = titular_member_input.get("firstName")
                    last_name = titular_member_input.get("lastName")
                    if first_name is None and created_proposer.display_name:
                        # Melhor QoL: se o membro titular não enviar firstName,
                        # usamos o displayName do proposer partido em dois
                        parts = created_proposer.display_name.split(None, 1)
                        first_name = parts[0] or None
                        last_name = (parts[1] if len(parts) > 1 else None) or last_name
                    # Beneficiário/titular herda email e telefone do proponente (nunca os pede);
                    # sem data própria, usa a do proponente individual.
                    date_of_birth = _as_date(titular_member_input.get("dateOfBirth")) or created_proposer.date_of_birth
                    created_member = create_member(
                        proposer=created_proposer,
                        relationship_code=relationship_code,
                        first_name=first_name,
                        last_name=last_name,
                        date_of_birth=date_of_birth,
                        sex_code=titular_member_input.get("sexCode"),
                        external_reference=(
                            titular_member_input.get("externalReference")
                            if "externalReference" in titular_member_input
                            else None
                        ),
                        attributes=(
                            titular_member_input.get("attributes")
                            if "attributes" in titular_member_input
                            else None
                        ),
                    )

            proposer = Proposer.objects.filter(id=proposer_id).first()
            plan = Plan.objects.filter(id=plan_id).first()
            if proposer is None or plan is None:
                raise ReferencedEntityNotFoundError("O cliente (proposerId) ou o plano (planId) indicado não existe neste tenant")
            if plan.status != PlanStatus.ACTIVE.value:
                # DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): reformulation of the
                # old OD-ANGOLA-009 ("versão antiga nunca inicia negócio novo") now
                # that there is no ProductVersion — an INACTIVE Plan can never
                # start new business, but a Quote already created against it keeps
                # working after it goes INACTIVE (same OD-ANGOLA-004 guarantee,
                # just expressed on the Plan instead of the version).
                raise ReferencedEntityNotFoundError(
                    f"O plano {plan_id} está em {plan.status}; só um plano ativo (ACTIVE) pode iniciar uma nova cotação"
                )

            # Sem data de efeito (decisão de 2026-10-15): a referência é o dia de criação.
            today = timezone_localdate()
            available, why = plan_availability(plan, today)
            if not available:
                raise ReferencedEntityNotFoundError(why)

            # Product Owner decision (2026-09-25): every Quote gets its `COT-N`
            # reference number immediately on creation, not only once APPROVED.
            # Previously this was assigned in decide_quote() and doubled as the
            # OD-ANGOLA-005 "apólice" (policy) number - it now means "cotação"
            # reference number for the whole lifecycle instead; nothing downstream
            # depends on it being null pre-approval (the customer portal login,
            # apps.customer_portal.application.auth_service._resolve_proposer,
            # already filters on `status="APPROVED"` explicitly, not on
            # quote_number being set, so a DRAFT quote's number is still unusable
            # there). Same safe, race-free numbering_service as document numbers.
            quote_number = next_continuous_value(sequence_code="QUOTE_NUMBER", prefix="COT-")

            quote = Quote.objects.create(
                tenant_id=tenant_id.value,
                proposer=proposer,
                plan=plan,
                status=QuoteStatus.DRAFT.value,
                quote_number=quote_number,
                valid_until=_default_valid_until(today),
                created_by=actor.actor_id if actor else "unknown",
            )
            _record_transition(quote, from_status=None, to_status=QuoteStatus.DRAFT.value)
            _audit.record(action="quote.created", entity_type="Quote", entity_id=str(quote.id))
            _outbox.append(
                aggregate_type="Quote",
                aggregate_id=str(quote.id),
                event_type="QUOTE.CREATED",
                payload={
                    "quoteId": str(quote.id),
                    "proposerId": str(proposer_id),
                    "productId": str(plan.product_id),
                    "planId": str(plan_id),
                    "validUntil": quote.valid_until.isoformat(),
                    "status": QuoteStatus.DRAFT.value,
                },
            )

            # Se criámos um titular no mesmo request, adicionamo-lo à cotação
            # imediatamente (a elegibilidade é avaliada em add_quote_member).
            if created_member is not None:
                correlation_id = None
                try:
                    from apps.foundation.interfaces.middleware import get_correlation_id as _get_cid

                    correlation_id = _get_cid()
                except Exception:
                    correlation_id = None
                quote = add_quote_member(quote=quote, member_id=created_member.id, correlation_id=correlation_id)
                quote.refresh_from_db()

    except Exception:
        # create_proposer / create_member gravam audit + outbox fora da
        # transaction.atomic()? Não: create_proposer já tem o seu próprio
        # atomic(). Por isso rollback da transaction aqui não reverte os
        # audit/outbox — mas isso é aceitável: um "orphan audit/outbox" é
        # irrelevante operacionalmente (não há FK e são históricos).
        # Não re-lançamos como novo erro.
        raise
    return quote


def _demote_to_draft_if_ready(quote: Quote) -> None:
    """QT-002 side effect: any material population/date edit invalidates a
    READY quote's readiness and its pricing reference."""
    if quote.status != QuoteStatus.READY.value:
        return
    updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.READY.value).update(
        status=QuoteStatus.DRAFT.value, latest_pricing_run=None, row_version=quote.row_version + 1
    )
    if updated:
        quote.refresh_from_db()
        _record_transition(quote, from_status=QuoteStatus.READY.value, to_status=QuoteStatus.DRAFT.value, reason_code="MATERIAL_EDIT")


def add_quote_member(*, quote: Quote, member_id: uuid.UUID, correlation_id: str | None) -> Quote:
    if quote.status not in (QuoteStatus.DRAFT.value, QuoteStatus.READY.value):
        raise QuoteStateError(
            f"A cotação {quote.id} está em {quote.status}; as pessoas seguras só podem ser alteradas em rascunho (DRAFT) ou pronta (READY). O estado {quote.status} indica que a cotação já foi submetida ou aprovada."
        )

    member = InsuredMember.objects.filter(id=member_id).first()
    if member is None:
        raise ReferencedEntityNotFoundError(
            f"memberId {member_id} does not exist for this tenant. Antes de adicionar um membro à "
            "cotação, crie primeiro o segurado no módulo de Clientes (ou use 'titularMemberInput' "
            "no 'createQuote' para criar o titular automaticamente junto com o proponente)."
        )
    if member.proposer_id != quote.proposer_id:
        # Caso frequente: o operador criou o proponente, mas esqueceu-se de associar o membro
        # TITULAR *ao mesmo proponente* (o membro está associado a outro proponente antigo).
        # Ajudar com uma mensagem clara.
        raise ReferencedEntityNotFoundError(
            f"memberId {member_id} pertence a um proponente diferente da cotação "
            f"(member.proposerId={member.proposer_id} vs quote.proposerId={quote.proposer_id}). "
            "Crie o membro TITULAR no mesmo proponente que vai contratar (é o tomador da apólice), "
            "ou use 'titularMemberInput' no createQuote para o backend criar os dois juntos."
        )
    if member.status != MemberStatus.ACTIVE.value:
        raise ReferencedEntityNotFoundError(
            f"memberId {member_id} is {member.status} and cannot be added to a quote. "
            "Ative o membro primeiro antes de o adicionar a cotações."
        )

    evaluation = EvaluateEligibilityUseCase().execute(
        proposer_id=quote.proposer_id,
        member_id=member.id,
        plan_id=quote.plan_id,
        effective_date=quote.reference_date,
        context={},
        correlation_id=correlation_id,
    )
    member_status = _ELIGIBILITY_TO_MEMBER_STATUS[evaluation.decision]

    try:
        with transaction.atomic():
            QuoteMember.objects.create(
                tenant_id=quote.tenant_id,
                quote=quote,
                member=member,
                status=member_status,
                eligibility_evaluation=evaluation,
            )
    except IntegrityError as exc:
        raise DuplicateMemberError(f"A pessoa segura {member_id} já está associada à cotação {quote.id}") from exc

    _demote_to_draft_if_ready(quote)
    _audit.record(
        action="quote.member_added",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata={"memberId": str(member_id), "eligibilityDecision": evaluation.decision, "quoteMemberStatus": member_status},
    )
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.POPULATION.UPDATED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "changeType": "MEMBER_ADDED",
            "memberId": str(member_id),
            "eligibilityDecision": evaluation.decision,
            "quoteMemberStatus": member_status,
        },
    )
    quote.refresh_from_db()
    return quote


def remove_quote_member(*, quote: Quote, member_id: uuid.UUID) -> None:
    if quote.status not in (QuoteStatus.DRAFT.value, QuoteStatus.READY.value):
        raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; as pessoas seguras só podem ser alteradas em rascunho (DRAFT) ou pronta (READY)")

    deleted, _ = QuoteMember.objects.filter(quote=quote, member_id=member_id).delete()
    if deleted == 0:
        raise ReferencedEntityNotFoundError(f"A pessoa segura {member_id} não está associada à cotação {quote.id}")

    _demote_to_draft_if_ready(quote)
    _audit.record(action="quote.member_removed", entity_type="Quote", entity_id=str(quote.id), metadata={"memberId": str(member_id)})
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.POPULATION.UPDATED",
        payload={
            "quoteId": str(quote.id),
            "changeType": "MEMBER_REMOVED",
            "memberId": str(member_id),
        },
    )


def active_adjustments_for_context(quote: Quote) -> list[dict]:
    """ACTIVE `QuoteAdjustment` rows in the shape the pricing engine reads
    (`context.adjustments`), oldest first so the order of application is
    stable and explainable."""
    return [
        {
            "id": str(adj.id),
            "kind": adj.kind,
            "value": str(adj.value),
            "scope": adj.scope,
            "memberId": str(adj.member_id) if adj.member_id else None,
            "reason": adj.reason,
        }
        for adj in QuoteAdjustment.objects.filter(quote=quote, status="ACTIVE").order_by("applied_at", "id")
    ]


def pre_existing_for_context(quote: Quote) -> dict[str, dict]:
    return {
        str(qm.member_id): qm.pre_existing_json
        for qm in quote.members.all()
        if qm.pre_existing_json
    }


def _age_on(date_of_birth: datetime.date, day: datetime.date) -> int:
    return day.year - date_of_birth.year - ((day.month, day.day) < (date_of_birth.month, date_of_birth.day))


def _first_adhesion_ages(members_by_id: dict) -> dict:
    """Idade de cada pessoa na sua 1.ª adesão: a data de inclusão mais antiga
    numa apólice (ou o início dessa apólice). Pessoas sem histórico ficam de
    fora — o motor regista que a idade de adesão não é conhecida."""
    from apps.policy.infrastructure.models import PolicyMember  # evita import circular quote <-> policy

    first: dict = {}
    rows = PolicyMember.objects.filter(member_id__in=list(members_by_id)).values_list(
        "member_id", "inclusion_date", "policy__start_date"
    )
    for member_id, inclusion_date, start_date in rows:
        day = inclusion_date or start_date
        if day is not None and (member_id not in first or day < first[member_id]):
            first[member_id] = day
    return {
        member_id: _age_on(members_by_id[member_id].date_of_birth, day)
        for member_id, day in first.items()
        if members_by_id[member_id].date_of_birth is not None
    }


def build_pricing_context(
    quote: Quote,
    *,
    selection: dict | None = None,
    adjustments: list[dict] | None = None,
    pre_existing: dict[str, dict] | None = None,
) -> tuple[dict, list[uuid.UUID]]:
    """The exact pricing `context` of a quote (and the member ids it prices).
    By default it reflects the quote's *saved* state (selection, ACTIVE
    adjustments, per-member pre-existing decisions); the keyword overrides
    let previews/scenarios ask "and if...?" without touching the quote."""
    priceable_member_ids = list(
        quote.members.filter(status__in=_PRICEABLE_MEMBER_STATUSES).values_list("member_id", flat=True)
    )
    members_by_id = {m.id: m for m in InsuredMember.objects.filter(id__in=priceable_member_ids)}

    context: dict = {
        "members": {
            str(member_id): (
                {"ageBand": band}
                if (band := compute_age_band(members_by_id[member_id].date_of_birth))
                else {}
            )
            for member_id in priceable_member_ids
        },
    }
    # Perfil actuarial do tomador (região, participação nos custos, venda
    # cruzada, renovação sem sinistralidade; e, em grupo, sector/adesão).
    # Vale para SAU e SAG: o Calculador do modelo aplica-o aos dois.
    # Tipo de apólice (âmbito das fórmulas do produto: «Tipos de Apólice»).
    context["policyType"] = "GROUP" if quote.proposer.proposer_type == "ORGANISATION" else "INDIVIDUAL"
    proposer_attributes = quote.proposer.attributes_json or {}
    actuarial_profile = proposer_attributes.get("actuarialProfile")
    if actuarial_profile is not None:
        if not isinstance(actuarial_profile, dict):
            raise ReferencedEntityNotFoundError("proposer.attributes.actuarialProfile tem de ser um objeto")
        context["actuarialProfile"] = actuarial_profile
    if quote.quote_type == "RENEWAL":
        context["quoteType"] = "RENEWAL"
        # A6: idade na 1.ª adesão (agravamento de adesão do modelo actuarial).
        for member_id, entry_age in _first_adhesion_ages(members_by_id).items():
            context["members"][str(member_id)]["entryAge"] = entry_age
    # A configuração de negócio publicada (pricing.*) tem prioridade; sem ela,
    # mantém-se a resolução legada RatingTable/PricingParameterSet.
    if BusinessConfigurationResolver.get("pricing.reference_premiums", effective_date=quote.reference_date) is None:
        context["ratingTableCode"] = resolve_default_rating_table_code(effective_date=quote.reference_date)
        context["parameterSetCode"] = resolve_default_parameter_set_code(effective_date=quote.reference_date)
    rule_version = resolve_pricing_rule_version_optional(effective_date=quote.reference_date)
    if rule_version:
        context["ruleVersionCode"] = rule_version
    chosen_selection = quote.selection_json if selection is None else selection
    if chosen_selection:
        context["selection"] = chosen_selection
    chosen_adjustments = active_adjustments_for_context(quote) if adjustments is None else adjustments
    if chosen_adjustments:
        context["adjustments"] = chosen_adjustments
    chosen_pre_existing = pre_existing_for_context(quote) if pre_existing is None else pre_existing
    if chosen_pre_existing:
        context["preExisting"] = chosen_pre_existing
    return context, priceable_member_ids


def _pricing_inputs_fingerprint(quote: Quote, context: dict, member_ids: list) -> str:
    """Impressão digital de tudo o que entra no cálculo da cotação, para saber
    se o último cálculo ainda vale. Inclui todas as configurações de negócio
    publicadas em vigor no dia de referência (tarifas, fórmulas, factores,
    regras, modelo actuarial, subscrição…), as tabelas/parâmetros/regras
    legados resolvidos, o conteúdo do plano (definições e coberturas) e os
    dados das pessoas."""
    from django.db.models import Q as _Q

    from apps.business_config.infrastructure.models import BusinessConfiguration
    from apps.foundation.application import platform_parameter_service, platform_reference_service
    from apps.pricing.application.rating_table_service import resolve_rating_table
    from apps.pricing.infrastructure.parameter_repository import resolve_pricing_parameter_set

    day = quote.reference_date
    configurations = sorted(
        [key, str(cid), version, checksum]
        for key, cid, version, checksum in BusinessConfiguration.objects.filter(
            tenant_id=quote.tenant_id, status="PUBLISHED", effective_from__lte=day
        )
        .filter(_Q(effective_to__isnull=True) | _Q(effective_to__gte=day))
        .values_list("config_key", "id", "version_no", "checksum")
    )
    legacy: dict[str, Any] = {}
    if context.get("ratingTableCode"):
        table = resolve_rating_table(code=context["ratingTableCode"], effective_date=day)
        legacy["ratingTable"] = [str(table.id), table.row_version] if table else None
    if context.get("parameterSetCode"):
        params = resolve_pricing_parameter_set(code=context["parameterSetCode"], effective_date=day)
        legacy["parameterSet"] = [str(params.id), params.row_version] if params else None
    people = sorted(
        [str(m.id), m.date_of_birth.isoformat() if m.date_of_birth else None, m.relationship_code, m.sex_code]
        for m in InsuredMember.objects.filter(id__in=member_ids)
    )
    payload = {
        "referenceDate": day.isoformat(),
        "configurations": configurations,
        "legacy": legacy,
        "plan": _plan_content_snapshot(quote.plan, quote.selection_json, day),
        "planRowVersion": quote.plan.row_version,
        "people": people,
        "context": context,
    }
    # Camada geral do fornecedor (impostos legais, limites): só entra quando
    # existe alguma versão publicada, para não invalidar cálculos antigos.
    platform_versions = platform_parameter_service.snapshot()
    if platform_versions:
        payload["platformParameters"] = platform_versions
    reference_tables = platform_reference_service.snapshot()
    if reference_tables:
        payload["platformReferenceTables"] = reference_tables
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def price_quote(*, quote: Quote, recalculate: bool, correlation_id: str | None):
    if quote.status not in (QuoteStatus.DRAFT.value, QuoteStatus.READY.value):
        extra = ""
        if quote.status == QuoteStatus.APPROVED.value or quote.status == QuoteStatus.BOUND.value:
            extra = (
                f" Esta cotação já foi aprovada; o prémio calculado antes da aprovação"
                f" já está congelado no snapshot. Para ver o prémio, use GET /quotes/{quote.id}"
                f" (campos 'premiumAnnualAmount' / 'premiumAnnualCurrency') e não tente recalcular."
                f" Para corrigir valores, devolva a cotação para READY primeiro (via decision=RETURN)."
            )
        elif quote.status == QuoteStatus.IN_REVIEW.value:
            extra = (
                " Cotação em análise (IN_REVIEW). Não é permitido recalculá-la enquanto"
                " um subscritor a estiver a rever. Primeiro devolva-a para READY via decision=RETURN."
            )
        raise QuoteStateError(
            f"A cotação {quote.id} está em {quote.status}; o cálculo do prémio só pode correr em rascunho (DRAFT) ou pronta (READY).{extra}"
        )

    context, priceable_member_ids = build_pricing_context(quote)
    fingerprint = _pricing_inputs_fingerprint(quote, context, priceable_member_ids)
    if not recalculate and quote.latest_pricing_run_id and quote.latest_pricing_run.status == "CALCULATED":
        # Reaproveita o último cálculo só se nada do que entra nele mudou:
        # configurações publicadas em vigor, plano e coberturas, pessoas,
        # escolhas e ajustes da cotação, e o dia de referência.
        last = (
            QuoteSnapshot.objects.filter(
                quote=quote, pricing_run_id=quote.latest_pricing_run_id, snapshot_type=QuoteSnapshotType.PRICING.value
            )
            .order_by("-snapshot_no")
            .first()
        )
        if last is not None and (last.snapshot_json or {}).get("inputsFingerprint") == fingerprint:
            return quote.latest_pricing_run

    pricing_run = calculate_pricing(
        plan_id=quote.plan_id,
        effective_date=quote.reference_date,
        member_ids=priceable_member_ids,
        context=context,
        correlation_id=correlation_id,
    )

    actor = CurrentActorProvider.get()
    snapshot_json = {
        "plan": _plan_content_snapshot(quote.plan, quote.selection_json, quote.reference_date),
        "referenceDate": quote.reference_date.isoformat(),
        "memberIds": [str(m) for m in priceable_member_ids],
        "context": context,
        "pricingRunId": str(pricing_run.id),
        "totalAmount": str(pricing_run.total_amount),
        "currencyCode": pricing_run.currency_code,
        "inputsFingerprint": fingerprint,
    }
    checksum = hashlib.sha256(json.dumps(snapshot_json, sort_keys=True).encode("utf-8")).hexdigest()
    next_snapshot_no = (
        QuoteSnapshot.objects.filter(quote=quote).order_by("-snapshot_no").values_list("snapshot_no", flat=True).first() or 0
    ) + 1
    QuoteSnapshot.objects.create(
        tenant_id=quote.tenant_id,
        quote=quote,
        snapshot_no=next_snapshot_no,
        snapshot_type=QuoteSnapshotType.PRICING.value,
        pricing_run=pricing_run,
        plan=quote.plan,
        snapshot_json=snapshot_json,
        checksum=checksum,
        created_by=actor.actor_id if actor else "unknown",
    )

    has_excluded_member = quote.members.filter(status=QuoteMemberStatus.EXCLUDED.value).exists()
    has_referral_member = quote.members.filter(status=QuoteMemberStatus.REFERRAL.value).exists()
    Quote.objects.filter(id=quote.id).update(latest_pricing_run=pricing_run, currency_code=pricing_run.currency_code)
    quote.refresh_from_db()

    from django.utils import timezone as _tz_now

    if quote.status == QuoteStatus.DRAFT.value or quote.status == QuoteStatus.READY.value:
        from_status = quote.status
        if has_excluded_member:
            new_status = QuoteStatus.REJECTED.value
            reason_code = "ELIGIBILITY_HARD_STOP"
            reason_text = "Cotação rejeitada automaticamente: pelo menos um membro foi considerado inelegível (HARD_STOP) após verificação de elegibilidade."
            Quote.objects.filter(id=quote.id).update(
                status=QuoteStatus.REJECTED.value,
                rejected_by=actor.actor_id if actor else "system:auto",
                rejected_at=_tz_now.now(),
            )
        elif has_referral_member:
            new_status = QuoteStatus.IN_REVIEW.value
            reason_code = "ELIGIBILITY_REFERRAL"
            reason_text = "Cotação encaminhada para análise manual: existem membros que requerem validação manual (documentação pendente, junta médica ou caso excepcional)."
            Quote.objects.filter(id=quote.id).update(
                status=QuoteStatus.IN_REVIEW.value,
                submitted_by=actor.actor_id if actor else "system:auto",
                submitted_at=_tz_now.now(),
            )
            if not ReviewTask.objects.filter(quote=quote, status__in=[ReviewTaskStatus.OPEN.value, ReviewTaskStatus.IN_PROGRESS.value]).exists():
                ReviewTask.objects.create(
                    tenant_id=quote.tenant_id,
                    quote=quote,
                    created_by=actor.actor_id if actor else "system:auto",
                )
        else:
            new_status = QuoteStatus.READY.value
            reason_code = "ELIGIBILITY_OK"
            reason_text = "Cotação pronta: todos os membros elegíveis, cálculo realizado com sucesso."
            if from_status != QuoteStatus.READY.value:
                Quote.objects.filter(id=quote.id).update(status=QuoteStatus.READY.value)

        quote.refresh_from_db()
        if from_status != new_status:
            _record_transition(
                quote,
                from_status=from_status,
                to_status=new_status,
                reason_code=reason_code,
                reason_text=reason_text,
                correlation_id=correlation_id,
            )
            _audit.record(
                action=f"quote.auto_status.{new_status.lower()}",
                entity_type="Quote",
                entity_id=str(quote.id),
                correlation_id=correlation_id,
                metadata={"reasonCode": reason_code, "reasonText": reason_text},
            )

    # R1: a calculation that leaves the editable state different from the
    # last saved version is itself a version (same state = nothing to save).
    from apps.quote.application import quote_version_service

    quote_version_service.record_version(quote=quote, source="PRICED")

    _audit.record(
        action="quote.priced",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata={"pricingRunId": str(pricing_run.id), "snapshotNo": next_snapshot_no, "status": quote.status},
    )
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.PRICE.CALCULATED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "pricingRunId": str(pricing_run.id),
            "totalAmount": str(pricing_run.total_amount),
            "currencyCode": pricing_run.currency_code,
            "snapshotNo": next_snapshot_no,
            "status": quote.status,
        },
    )
    return pricing_run


def resolve_pricing_rule_version_optional(*, effective_date: datetime.date) -> str | None:
    """PRICING rule adjustments are optional (Q360-S5-01) — unlike the
    rating table/parameter set, an ambiguous or absent one simply means no
    adjustment is applied, it never blocks pricing."""
    from apps.foundation.infrastructure.models import RuleVersion
    from django.db.models import Q as _Q

    codes = list(
        RuleVersion.objects.filter(
            rule_set__rule_domain="PRICING", status="PUBLISHED", effective_from__lte=effective_date
        )
        .filter(_Q(effective_to__isnull=True) | _Q(effective_to__gte=effective_date))
        .values_list("rule_set__code", flat=True)
        .distinct()
    )
    distinct = sorted(set(codes))
    return distinct[0] if len(distinct) == 1 else None


def delete_quote(*, quote: Quote) -> None:
    """Apaga uma cotação e tudo o que está "dentro" dela (membros, ajustes,
    snapshots, state_history, cenários, tarefas de revisão). Só permitido
    para estados não-protegidos (ciclo de vida ainda não saiu do staff).

    Permitido deletar: DRAFT / READY / REJECTED / EXPIRED / CANCELLED.
    Bloqueado: IN_REVIEW (tem tarefa de review pendente), APPROVED / BOUND
    (já houve decisão de aprovador e pode existir Policy emitida). Nestes
    casos levanta QuoteDeletionBlockedError."""

    actor = CurrentActorProvider.get()
    protected = {
        QuoteStatus.IN_REVIEW.value,
        QuoteStatus.APPROVED.value,
        QuoteStatus.BOUND.value,
    }
    if quote.status in protected:
        raise QuoteDeletionBlockedError(
            f"Quote {quote.id} cannot be deleted because it is in status {quote.status}. "
            "Cotações em análise, aprovadas ou emitidas não podem ser apagadas para "
            "preservar a trilha de auditoria e documentos relacionados. "
            "Para cotações em análise: decida RETURN (volta a READY) e depois apague, "
            "ou use CANCEL/REJECT para registar o encerramento formal da cotação."
        )
    with transaction.atomic():
        # Estes rel. têm on_delete=CASCADE/DO_NOTHING misturados. Para segurança
        # apagamos tudo explicitamente antes da Quote:
        QuoteMember.objects.filter(quote=quote).delete()
        QuoteAdjustment.objects.filter(quote=quote).delete()
        ReviewTask.objects.filter(quote=quote).delete()
        QuoteDecision.objects.filter(quote=quote).delete()
        QuoteSnapshot.objects.filter(quote=quote).delete()
        QuoteStateHistory.objects.filter(quote=quote).delete()
        # Cenários (QuoteScenario) tem on_delete CASCADE no modelo.
        # Apagamos pelo ORM para disparar qualquer listener futuro:
        quote.scenarios.all().delete()  # type: ignore[attr-defined]
        # Finalmente a própria cotação:
        Quote.objects.filter(id=quote.id).delete()
    _audit.record(
        action="quote.deleted",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata={"quoteNumber": quote.quote_number, "statusDeleted": quote.status},
    )
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.DELETED",
        payload={
            "quoteId": str(quote.id),
            "quoteNumber": quote.quote_number,
            "deletedBy": actor.actor_id if actor else "unknown",
            "statusDeleted": quote.status,
        },
    )


# ---------------------------------------------------------------------------
# Q360-S7-01..03 — submission, review workspace, decision (approve/reject/
# return). See ART-009 "Quote Machine" (QT-003..006) and "Review Machine"
# (RV-001..005), and DECISIONS_TAKEN.md#S07-REVIEW-001 for the judgment
# calls made here (no START_REVIEW/authority-policy endpoint in ART-006).
# ---------------------------------------------------------------------------


def _create_snapshot(*, quote: Quote, snapshot_type: str) -> QuoteSnapshot:
    """Captures the quote's current (already-calculated) pricing reference
    at a lifecycle milestone — SUBMISSION (QT-003) / APPROVAL (QT-004) —
    without recalculating anything (the snapshot must reflect exactly what
    was priced, not a fresh run)."""
    actor = CurrentActorProvider.get()
    snapshot_json = {
        "status": quote.status,
        "plan": _plan_content_snapshot(quote.plan, quote.selection_json, quote.reference_date),
        "referenceDate": quote.reference_date.isoformat(),
        "latestPricingRunId": str(quote.latest_pricing_run_id) if quote.latest_pricing_run_id else None,
    }
    checksum = hashlib.sha256(json.dumps(snapshot_json, sort_keys=True).encode("utf-8")).hexdigest()
    next_snapshot_no = (
        QuoteSnapshot.objects.filter(quote=quote).order_by("-snapshot_no").values_list("snapshot_no", flat=True).first() or 0
    ) + 1
    return QuoteSnapshot.objects.create(
        tenant_id=quote.tenant_id,
        quote=quote,
        snapshot_no=next_snapshot_no,
        snapshot_type=snapshot_type,
        pricing_run=quote.latest_pricing_run,
        plan=quote.plan,
        snapshot_json=snapshot_json,
        checksum=checksum,
        created_by=actor.actor_id if actor else "unknown",
    )


def submit_quote(*, quote: Quote, row_version: int, correlation_id: str | None) -> Quote:
    """QT-003: READY -> IN_REVIEW. Guard ("valid pricing + immutable
    submission snapshot + prerequisites satisfied") is exactly what
    becoming READY already proved (see price_quote) - submit just requires
    the quote to still be READY."""
    if quote.status != QuoteStatus.READY.value:
        raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; só uma cotação pronta (READY) pode ser submetida")

    # Plan-level underwriting rules (group minimum size, age limits,
    # household) — only evaluated for plans that configured them.
    from apps.quote.application import requirements_service

    requirements_service.enforce_requirements(quote)

    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.READY.value, row_version=row_version).update(
        status=QuoteStatus.IN_REVIEW.value, submitted_by=actor_id, submitted_at=timezone_now(), row_version=row_version + 1
    )
    if updated == 0:
        # Distinguish "someone else changed it" (VERSION-CONFLICT) from
        # "it's no longer READY" (QUOTE-STATE) — re-check which happened.
        quote.refresh_from_db()
        if quote.status != QuoteStatus.READY.value:
            raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; só uma cotação pronta (READY) pode ser submetida")
        raise RowVersionMismatchError(f"A versão da cotação {quote.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo")
    quote.refresh_from_db()

    ReviewTask.objects.create(tenant_id=quote.tenant_id, quote=quote, created_by=actor_id)
    _create_snapshot(quote=quote, snapshot_type=QuoteSnapshotType.SUBMISSION.value)
    _record_transition(
        quote, from_status=QuoteStatus.READY.value, to_status=QuoteStatus.IN_REVIEW.value, correlation_id=correlation_id
    )
    _audit.record(action="quote.submitted", entity_type="Quote", entity_id=str(quote.id))
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.SUBMITTED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "submittedBy": actor_id,
            "submittedAt": quote.submitted_at.isoformat() if quote.submitted_at else None,
        },
    )
    return quote


def get_active_review_task(*, quote: Quote) -> ReviewTask | None:
    return quote.review_tasks.order_by("-created_at").first()


def get_quote_history(*, quote: Quote):
    return quote.state_history.order_by("changed_at")


def _resolve_authority_limit(*, effective_date: datetime.date) -> "tuple[AuthorityPolicy | None, str | None]":
    """OD-005 — genuinely open, see DECISIONS_TAKEN.md#S07-REVIEW-001. No
    PUBLISHED AuthorityPolicy means "no configured limit", not fail-closed
    (unlike eligibility): scope (`q360.approve`) + DOC-001 `quote:approve`
    already gate *who* may approve at all; this only narrows *how much*
    once OD-005 names a real policy."""
    from django.db.models import Q as _Q

    policy = (
        AuthorityPolicy.objects.filter(status="PUBLISHED", effective_from__lte=effective_date)
        .filter(_Q(effective_to__isnull=True) | _Q(effective_to__gte=effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )
    if policy is None:
        return None, None
    max_amount = policy.policy_json.get("maxApprovalAmount")
    return policy, max_amount


def decide_quote(
    *,
    quote: Quote,
    decision: str,
    reason_code: str,
    reason_text: str | None,
    row_version: int,
    correlation_id: str | None,
) -> Quote:
    if quote.status != QuoteStatus.IN_REVIEW.value:
        raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; só uma cotação em revisão (IN_REVIEW) pode ser decidida")

    review_task = get_active_review_task(quote=quote)
    if review_task is None or review_task.status not in (ReviewTaskStatus.OPEN.value, ReviewTaskStatus.IN_PROGRESS.value):
        raise QuoteStateError(f"A cotação {quote.id} não tem nenhuma tarefa de revisão ativa")

    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"

    # Segregation of duties (Q360-S7-01 AC "Submitter não aprova"; ART-012
    # V019 `ck_quote_four_eyes` / V023 `ck_decision_four_eyes` enforce this
    # at the DB level for every decision type, not just APPROVE - checked
    # here first for a clean SEC-403 instead of a raw IntegrityError.
    if quote.submitted_by and quote.submitted_by == actor_id:
        raise SegregationOfDutiesError(
            f"O utilizador {actor_id} submeteu a cotação {quote.id} e não pode decidir sobre ela (regra dos quatro olhos)"
        )

    authority_policy = None
    if decision == QuoteDecisionType.APPROVE.value:
        # Regras de fluxo (`rules.custom`, etapa WORKFLOW): certas cotações só
        # podem ser aprovadas por um perfil (ex.: Gestor de subscrição acima de
        # um prémio). Um ADMIN pode sempre.
        from apps.quote.application import requirements_service

        required_roles = requirements_service.required_approval_roles(quote)
        actor_roles = {getattr(r, "value", r) for r in (actor.roles if actor else ())}
        if required_roles and not actor_roles & {*required_roles, "ADMIN"}:
            raise SegregationOfDutiesError(
                f"A cotação {quote.id} só pode ser aprovada pelo perfil: {', '.join(required_roles)} "
                "(regra de fluxo configurada)"
            )
        authority_policy, max_amount = _resolve_authority_limit(effective_date=quote.reference_date)
        if max_amount is not None and quote.latest_pricing_run and quote.latest_pricing_run.total_amount is not None:
            from decimal import Decimal

            if quote.latest_pricing_run.total_amount > Decimal(str(max_amount)):
                raise SegregationOfDutiesError(
                    f"O total da cotação {quote.id} excede a autoridade de aprovação configurada na política {authority_policy.code}"
                )

    target_status = {
        QuoteDecisionType.APPROVE.value: QuoteStatus.APPROVED.value,
        QuoteDecisionType.REJECT.value: QuoteStatus.REJECTED.value,
        QuoteDecisionType.RETURN.value: QuoteStatus.READY.value,
    }[decision]
    review_target_status = {
        QuoteDecisionType.APPROVE.value: ReviewTaskStatus.DECIDED.value,
        QuoteDecisionType.REJECT.value: ReviewTaskStatus.DECIDED.value,
        QuoteDecisionType.RETURN.value: ReviewTaskStatus.RETURNED.value,
    }[decision]

    with transaction.atomic():
        quote_fields = {"status": target_status, "row_version": row_version + 1}
        if decision == QuoteDecisionType.APPROVE.value:
            quote_fields.update(approved_by=actor_id, approved_at=timezone_now())
            if not quote.quote_number:
                # Product Owner decision (2026-09-25): `quote_number` is
                # now assigned in create_quote() instead, so this only
                # ever fires as a backfill for a Quote created before that
                # change. Sequential test/demo number via the same safe,
                # race-free numbering_service already used for document
                # numbers (DECISIONS_TAKEN.md#S06-QUOTE-001 item 4) — NOT a
                # real ARSEG policy-number format (ART-011 PROH-008 still
                # prohibits inventing one), just enough of a stable,
                # unique identifier for the lookup-by-number flow to work.
                quote_fields["quote_number"] = next_continuous_value(sequence_code="QUOTE_NUMBER", prefix="COT-")
        elif decision == QuoteDecisionType.REJECT.value:
            quote_fields.update(rejected_by=actor_id, rejected_at=timezone_now())
        updated = Quote.objects.filter(id=quote.id, status=QuoteStatus.IN_REVIEW.value, row_version=row_version).update(
            **quote_fields
        )
        if updated == 0:
            quote.refresh_from_db()
            if quote.status != QuoteStatus.IN_REVIEW.value:
                raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; só uma cotação em revisão (IN_REVIEW) pode ser decidida")
            raise RowVersionMismatchError(f"A versão da cotação {quote.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo")

        ReviewTask.objects.filter(id=review_task.id).update(status=review_target_status, decided_at=timezone_now())
        quote.refresh_from_db()

        snapshot = None
        if decision == QuoteDecisionType.APPROVE.value:
            snapshot = _create_snapshot(quote=quote, snapshot_type=QuoteSnapshotType.APPROVAL.value)

        QuoteDecision.objects.create(
            tenant_id=quote.tenant_id,
            quote=quote,
            review_task=review_task,
            authority_policy=authority_policy,
            decision=decision,
            reason_code=reason_code,
            reason_text=reason_text,
            decided_by=actor_id,
            submitted_by=quote.submitted_by,
            snapshot=snapshot,
        )

    from_status = QuoteStatus.IN_REVIEW.value
    _record_transition(
        quote, from_status=from_status, to_status=target_status, reason_code=reason_code, reason_text=reason_text,
        correlation_id=correlation_id,
    )
    _audit.record(
        action=f"quote.decision.{decision.lower()}",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata={"reasonCode": reason_code, "decidedBy": actor_id},
    )
    event_type_map = {
        QuoteDecisionType.APPROVE.value: "QUOTE.APPROVED",
        QuoteDecisionType.REJECT.value: "QUOTE.REJECTED",
        QuoteDecisionType.RETURN.value: "QUOTE.RETURNED",
    }
    outbox_payload = {
        "quoteId": str(quote.id),
        "decision": decision,
        "reasonCode": reason_code,
        "reasonText": reason_text,
        "decidedBy": actor_id,
    }
    if decision == QuoteDecisionType.APPROVE.value:
        outbox_payload["approvedAt"] = quote.approved_at.isoformat() if quote.approved_at else None
    elif decision == QuoteDecisionType.REJECT.value:
        outbox_payload["rejectedAt"] = quote.rejected_at.isoformat() if quote.rejected_at else None
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type=event_type_map[decision],
        correlation_id=correlation_id,
        payload=outbox_payload,
    )
    return quote


# ---------------------------------------------------------------------------
# Q360-S8-03 — cancellation (user-initiated) and expiry (system scheduler).
# Both allowed from the same source set per ART-009's Quote Machine
# (QT-007..010 for CANCEL, QT-011..014 for EXPIRE): DRAFT, READY,
# IN_REVIEW, APPROVED. REJECTED/EXPIRED/CANCELLED are terminal (ART-009
# "Forbidden Transitions").
# ---------------------------------------------------------------------------

CANCELLABLE_QUOTE_STATUSES = (
    QuoteStatus.DRAFT.value,
    QuoteStatus.READY.value,
    QuoteStatus.IN_REVIEW.value,
    QuoteStatus.APPROVED.value,
)


def cancel_quote(*, quote: Quote, reason_code: str, reason_text: str | None, row_version: int, correlation_id: str | None) -> Quote:
    if quote.status not in CANCELLABLE_QUOTE_STATUSES:
        raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; não pode ser cancelada neste estado")

    from_status = quote.status
    updated = Quote.objects.filter(id=quote.id, status=from_status, row_version=row_version).update(
        status=QuoteStatus.CANCELLED.value, cancellation_reason=reason_text or reason_code, row_version=row_version + 1
    )
    if updated == 0:
        quote.refresh_from_db()
        if quote.status not in CANCELLABLE_QUOTE_STATUSES:
            raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; não pode ser cancelada neste estado")
        raise RowVersionMismatchError(f"A versão da cotação {quote.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo")
    quote.refresh_from_db()

    # QT-009's "Close/void active review task consistently" has no clean
    # target status in ART-012's `ck_review_status` (only OPEN/IN_PROGRESS/
    # DECIDED/RETURNED - none means "voided") - left untouched rather than
    # forcing a semantically wrong value. See DECISIONS_TAKEN.md#S08-DOCUMENT-001.

    _record_transition(
        quote, from_status=from_status, to_status=QuoteStatus.CANCELLED.value, reason_code=reason_code,
        reason_text=reason_text, correlation_id=correlation_id,
    )
    _audit.record(action="quote.cancelled", entity_type="Quote", entity_id=str(quote.id), metadata={"reasonCode": reason_code})
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.CANCELLED",
        correlation_id=correlation_id,
        payload={
            "quoteId": str(quote.id),
            "reasonCode": reason_code,
            "reasonText": reason_text,
        },
    )
    return quote


def expire_quote(*, quote: Quote) -> Quote | None:
    """QT-011..014, actor "System Scheduler" (ART-009 Commands & Authority:
    "No user-supplied actor"). Called by `manage.py expire_quotes` (no
    background task queue exists in this stack - a cron/scheduled-task
    invocation of that command is the deployment's responsibility, same
    "no messaging without a real consumer" posture as everywhere else in
    this project). Returns None (no-op) if the quote isn't actually due."""
    if quote.status not in CANCELLABLE_QUOTE_STATUSES or quote.valid_until is None or quote.valid_until >= datetime.date.today():
        return None

    from_status = quote.status
    updated = Quote.objects.filter(id=quote.id, status=from_status).update(status=QuoteStatus.EXPIRED.value)
    if updated == 0:
        return None
    quote.refresh_from_db()

    _record_transition(quote, from_status=from_status, to_status=QuoteStatus.EXPIRED.value, reason_code="VALIDITY_ELAPSED")
    _audit.record(action="quote.expired", entity_type="Quote", entity_id=str(quote.id))
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.EXPIRED",
        payload={
            "quoteId": str(quote.id),
            "validUntil": quote.valid_until.isoformat() if quote.valid_until else None,
            "fromStatus": from_status,
        },
    )
    return quote


# ---------------------------------------------------------------------------
# Reutilização de cotações rejeitadas (2026-10): REJECTED -> DRAFT.
# Uma cotação rejeitada (automaticamente por um membro inelegível, ou numa
# decisão de revisão) pode ser reaberta para corrigir a população/dados e
# voltar ao ciclo normal (reprecificar -> READY -> submeter), mantendo o
# número da cotação, o histórico e a trilha de auditoria. Para criar uma
# NOVA cotação a partir dela continua a existir `POST /quotes/{id}/clone`.
# ---------------------------------------------------------------------------


def reopen_quote(*, quote: Quote, reason: str | None, row_version: int, correlation_id: str | None) -> Quote:
    from apps.foundation.application.change_audit import change_metadata, require_reason
    from apps.quote.infrastructure.models import QuoteMember as _QuoteMember

    reason = require_reason(reason)
    if quote.status != QuoteStatus.REJECTED.value:
        raise QuoteStateError(
            f"A cotação {quote.id} está em {quote.status}; só uma cotação rejeitada (REJECTED) pode ser reaberta"
        )

    today = datetime.date.today()
    updates: dict[str, Any] = {
        "status": QuoteStatus.DRAFT.value,
        "latest_pricing_run": None,
        "rejected_by": None,
        "rejected_at": None,
        "submitted_by": None,
        "submitted_at": None,
        "row_version": row_version + 1,
    }
    if quote.valid_until is None or quote.valid_until < today:
        # A validade caducou entretanto: renova-a a partir do dia da reabertura.
        updates["valid_until"] = _default_valid_until(today)

    with transaction.atomic():
        changed = Quote.objects.filter(
            id=quote.id, status=QuoteStatus.REJECTED.value, row_version=row_version
        ).update(**updates)
        if changed == 0:
            quote.refresh_from_db()
            if quote.status != QuoteStatus.REJECTED.value:
                raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; só uma cotação rejeitada (REJECTED) pode ser reaberta")
            raise RowVersionMismatchError(
                f"A versão da cotação {quote.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
            )
        quote.refresh_from_db()

        # Os dados das pessoas podem ter sido corrigidos desde a rejeição:
        # reavalia a elegibilidade de cada uma com os dados atuais.
        for quote_member in _QuoteMember.objects.filter(quote=quote).select_related("member"):
            evaluation = EvaluateEligibilityUseCase().execute(
                proposer_id=quote.proposer_id,
                member_id=quote_member.member_id,
                plan_id=quote.plan_id,
                effective_date=quote.reference_date,
                context={},
                correlation_id=correlation_id,
            )
            _QuoteMember.objects.filter(id=quote_member.id).update(
                status=_ELIGIBILITY_TO_MEMBER_STATUS[evaluation.decision], eligibility_evaluation=evaluation
            )

        _record_transition(
            quote,
            from_status=QuoteStatus.REJECTED.value,
            to_status=QuoteStatus.DRAFT.value,
            reason_code="REOPENED",
            reason_text=reason,
            correlation_id=correlation_id,
        )

    _audit.record(
        action="quote.reopened",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(after={"status": QuoteStatus.DRAFT.value}, reason=reason),
    )
    _outbox.append(
        aggregate_type="Quote",
        aggregate_id=str(quote.id),
        event_type="QUOTE.REOPENED",
        correlation_id=correlation_id,
        payload={"quoteId": str(quote.id), "fromStatus": QuoteStatus.REJECTED.value, "reason": reason},
    )
    return quote
