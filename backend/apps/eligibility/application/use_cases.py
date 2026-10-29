"""EvaluateEligibilityUseCase (DOC-004 s9). Orchestrates: resolve
referenced entities -> resolve applicable rule version -> run the pure
`domain.evaluation.evaluate()` -> persist an immutable
`EligibilityEvaluation` snapshot (DOC-004 s9: "Resultado deve guardar
versão do rule set.").
"""
from __future__ import annotations

import dataclasses
import datetime
import uuid
from typing import Any

from apps.client.domain.enums import ProposerType
from apps.client.infrastructure.models import InsuredMember, Proposer, RelationshipCode
from apps.eligibility.domain.errors import ReferencedEntityNotFoundError
from apps.eligibility.domain.enums import EligibilityDecision
from apps.eligibility.domain.evaluation import (
    AngolaEvidence,
    EligibilityMessage,
    EvaluationInput,
    LegalAgeLimits,
    PlanFacts,
    _age_on,
    evaluate,
)
from apps.eligibility.infrastructure.models import EligibilityEvaluation
from apps.eligibility.infrastructure.rule_repository import parse_config, resolve_eligibility_rule_version
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.infrastructure.models import Plan

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()


def _with_member_evidence(context: dict[str, Any] | None, member: InsuredMember | None) -> dict[str, Any]:
    """Junta à evidência de quem chama a que vem dos documentos aprovados da pessoa
    (só acrescenta; nunca retira nem substitui o que foi indicado)."""
    if member is None:
        return context or {}
    from apps.client.application.member_document_service import evidence_for

    found = evidence_for(member)
    if not found:
        return context or {}
    merged = dict(context or {})
    angola = dict(merged.get("angola") or {})
    for key, value in found.items():
        if key == "unionBondType":
            angola.setdefault(key, value)
        elif value:
            angola[key] = True
    merged["angola"] = angola
    return merged


# Decisões que uma regra "Quando… então…" de elegibilidade ainda pode
# agravar (nunca desfaz um bloqueio nem uma pendência do motor).
_CUSTOM_RULE_OVERRIDABLE = {EligibilityDecision.ELIGIBLE, EligibilityDecision.WARNING}


def _apply_custom_rules(
    *, decision: EligibilityDecision, messages: list, member: InsuredMember | None, plan: Plan,
    relationship_category: str | None, effective_date: datetime.date,
):
    """Regras `rules.custom` da etapa ELIGIBILITY (por pessoa): NOT_ELIGIBLE
    bloqueia (HARD_STOP); REFER_TO_UNDERWRITING encaminha (REFERRAL)."""
    from apps.business_config.application.custom_rules import load_published_rules, person_facts
    from apps.business_config.application.overlays import effective_plan_settings
    from apps.business_config.domain.custom_rules import describe as describe_rule

    published = load_published_rules(effective_date, plan.product_id)
    rules = published.for_stage("ELIGIBILITY", "PERSON")
    if not rules or decision not in _CUSTOM_RULE_OVERRIDABLE:
        return decision, messages, published.version
    facts = person_facts(
        age=_age_on(member.date_of_birth) if member is not None and member.date_of_birth else None,
        members_count=None, plan_code=str(plan.code), plan_name=str(plan.name),
        dimensions={"segment": effective_plan_settings(plan, effective_date).get("segment")},
        relationship=relationship_category, product=(plan.product.code, plan.product.name),
    )
    matched = [r for r in rules if r.matches(facts)]
    blocking = [r for r in matched if r.action == "NOT_ELIGIBLE"]
    chosen = blocking or matched
    if not chosen:
        return decision, messages, published.version
    new_decision = EligibilityDecision.HARD_STOP if blocking else EligibilityDecision.REFERRAL
    severity = "ERROR" if blocking else "WARNING"
    extra = [EligibilityMessage("ELIG-CUSTOM-RULE", severity, r.message or describe_rule(r)) for r in chosen]
    return new_decision, [*messages, *extra], published.version


def _with_product_age_limits(config, plan: Plan, effective_date: datetime.date):
    """Idades de entrada em cascata: as de `product.age_limits` (versão do
    produto ou geral; a linha do plano prevalece sobre a linha sem plano)
    sobrepõem-se às da regra de elegibilidade geral. Sem linhas, nada muda."""
    if config is None:
        return None
    from apps.business_config.application.overlays import age_limits
    from apps.business_config.application.readers import BusinessSnapshot

    limits = age_limits(plan, plan.settings_json or {}, BusinessSnapshot.load(effective_date).for_product(plan.product_id))
    if "entryMin" not in limits and "entryMax" not in limits:
        return config
    return dataclasses.replace(
        config,
        min_entry_age=limits.get("entryMin", config.min_entry_age),
        max_entry_age=limits.get("entryMax", config.max_entry_age),
    )


class EvaluateEligibilityUseCase:
    def execute(
        self,
        *,
        proposer_id: uuid.UUID | None,
        member_id: uuid.UUID | None,
        plan_id: uuid.UUID,
        effective_date: datetime.date,
        context: dict[str, Any],
        correlation_id: str | None,
    ) -> EligibilityEvaluation:
        tenant_id = CurrentTenantProvider.require()

        proposer = Proposer.objects.filter(id=proposer_id).first() if proposer_id else None
        member = InsuredMember.objects.filter(id=member_id).first() if member_id else None
        plan = Plan.objects.filter(id=plan_id).first()
        
        if proposer_id and proposer is None:
            raise ReferencedEntityNotFoundError("O cliente (proposerId) indicado não existe neste tenant")
        if member_id and member is None:
            raise ReferencedEntityNotFoundError("A pessoa segura (memberId) indicada não existe neste tenant")
        if member is not None and proposer_id and member.proposer_id != proposer_id:
            raise ReferencedEntityNotFoundError("A pessoa segura (memberId) não pertence ao cliente (proposerId) indicado")


        if plan is None:
            raise ReferencedEntityNotFoundError("O plano (planId) indicado não existe neste tenant")

        # Documentos de suporte já aprovados (certificado de matrícula, prova de
        # união…) entram como evidência: assim a pendência resolve-se sozinha.
        context = _with_member_evidence(context, member)

        rule_version = resolve_eligibility_rule_version(effective_date)
        config = _with_product_age_limits(parse_config(rule_version) if rule_version else None, plan, effective_date)

        # MOTOR_ELEGIBILIDADE.md Fase A: resolve the RelationshipCode
        # category (OD-ANGOLA-010 catalog, already tenant-scoped) and, for
        # a corporate group policy, the sponsoring organisation's Proposer
        # id — both feed EligibilityRuleConfig.category_rule_for. Evidence
        # flags are read from the request's existing `context` payload,
        # never fabricated here (Fase B/C are still open on where that
        # evidence is verified/stored).
        relationship_category = None
        if member and member.relationship_code:
            relationship_category = (
                RelationshipCode.objects.filter(code=member.relationship_code)
                .values_list("category", flat=True)
                .first()
            )
        organisation_proposer_id = (
            str(proposer.id) if proposer and proposer.proposer_type == ProposerType.ORGANISATION.value else None
        )

        data = EvaluationInput(
            member_id=str(member.id) if member else (str(member_id) if member_id else None),
            relationship_code=member.relationship_code if member else None,
            date_of_birth=member.date_of_birth if member else None,
            plan_id=str(plan_id),
            effective_date=effective_date,
            relationship_category=relationship_category,
            organisation_proposer_id=organisation_proposer_id,
            angola_evidence=AngolaEvidence.from_dict(context.get("angola") if context else None),
        )
        plan_facts = PlanFacts(is_active=plan.status == "ACTIVE")

        from apps.foundation.application import system_parameter_service

        legal = LegalAgeLimits(
            age_of_majority=system_parameter_service.get_value("legal.age_of_majority"),
            max_age_with_proof=system_parameter_service.get_value("limits.dependent_max_age_with_proof"),
        )
        decision, messages = evaluate(data=data, plan=plan_facts, config=config, legal=legal)
        decision, messages, custom_rules_version = _apply_custom_rules(
            decision=decision, messages=list(messages), member=member, plan=plan,
            relationship_category=relationship_category, effective_date=effective_date,
        )

        evaluation = EligibilityEvaluation.objects.create(
            tenant_id=tenant_id.value,
            proposer=proposer,
            member=member,
            plan=plan,
            rule_version=rule_version,
            decision=decision.value,
            input_snapshot_json={
                "proposerId": str(proposer_id) if proposer_id else None,
                "memberId": str(member_id) if member_id else None,
                "planId": str(plan_id),
                "effectiveDate": effective_date.isoformat(),
                "context": context,
                "customRulesVersion": custom_rules_version,
            },
            evidence_json=[
                {"code": m.code, "severity": m.severity, "message": m.message} for m in messages
            ],
            correlation_id=correlation_id,
        )

        _audit.record(
            action="eligibility.evaluated",
            entity_type="EligibilityEvaluation",
            entity_id=str(evaluation.id),
            correlation_id=correlation_id,
            metadata={
                "decision": decision.value,
                "memberId": str(member_id) if member_id else None,
                "proposerId": str(proposer_id) if proposer_id else None,
                "productId": str(plan.product_id),
                "planId": str(plan_id),
                "ruleVersionId": str(rule_version.id) if rule_version else None,
            },
        )
        _outbox.append(
            aggregate_type="EligibilityEvaluation",
            aggregate_id=str(evaluation.id),
            event_type="ELIGIBILITY.EVALUATED",
            correlation_id=correlation_id,
            payload={
                "evaluationId": str(evaluation.id),
                "decision": decision.value,
                "memberId": str(member_id) if member_id else None,
                "proposerId": str(proposer_id) if proposer_id else None,
                "productId": str(plan.product_id),
                "planId": str(plan_id),
                "effectiveDate": effective_date.isoformat(),
            },
        )
        return evaluation
