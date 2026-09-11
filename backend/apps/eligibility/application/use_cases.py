"""EvaluateEligibilityUseCase (DOC-004 s9). Orchestrates: resolve
referenced entities -> resolve applicable rule version -> run the pure
`domain.evaluation.evaluate()` -> persist an immutable
`EligibilityEvaluation` snapshot (DOC-004 s9: "Resultado deve guardar
versão do rule set.").
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.domain.errors import ReferencedEntityNotFoundError
from apps.eligibility.domain.evaluation import EvaluationInput, PlanFacts, ProductVersionFacts, evaluate
from apps.eligibility.infrastructure.models import EligibilityEvaluation
from apps.eligibility.infrastructure.rule_repository import parse_config, resolve_eligibility_rule_version
from apps.foundation.application.context import CurrentTenantProvider
from apps.product.infrastructure.models import Plan, ProductVersion


class EvaluateEligibilityUseCase:
    def execute(
        self,
        *,
        proposer_id: uuid.UUID | None,
        member_id: uuid.UUID | None,
        product_version_id: uuid.UUID,
        plan_id: uuid.UUID,
        effective_date: datetime.date,
        context: dict[str, Any],
        correlation_id: str | None,
    ) -> EligibilityEvaluation:
        tenant_id = CurrentTenantProvider.require()

        proposer = Proposer.objects.filter(id=proposer_id).first() if proposer_id else None
        member = InsuredMember.objects.filter(id=member_id).first() if member_id else None
        product_version = ProductVersion.objects.filter(id=product_version_id).first()
        plan = Plan.objects.filter(id=plan_id).first()

        # ART-005 `eligibility_evaluation.product_version_id`/`plan_id` are
        # NOT NULL: an evaluation cannot be persisted at all without both,
        # so this is a request error (400), not a HARD_STOP decision to
        # record — see domain/errors.py ReferencedEntityNotFoundError.
        if product_version is None or plan is None:
            raise ReferencedEntityNotFoundError(
                "Referenced productVersionId or planId does not exist for this tenant"
            )

        rule_version = resolve_eligibility_rule_version(effective_date)
        config = parse_config(rule_version) if rule_version else None

        data = EvaluationInput(
            member_id=str(member.id) if member else (str(member_id) if member_id else None),
            relationship_code=member.relationship_code if member else None,
            date_of_birth=member.date_of_birth if member else None,
            product_version_id=str(product_version_id),
            plan_id=str(plan_id),
            effective_date=effective_date,
        )
        pv_facts = ProductVersionFacts(
            effective_from=product_version.effective_from, effective_to=product_version.effective_to
        )
        plan_facts = PlanFacts(is_active=plan.status == "ACTIVE")

        decision, messages = evaluate(data=data, product_version=pv_facts, plan=plan_facts, config=config)

        evaluation = EligibilityEvaluation.objects.create(
            tenant_id=tenant_id.value,
            proposer=proposer,
            member=member,
            product_version=product_version,
            plan=plan,
            rule_version=rule_version,
            decision=decision.value,
            input_snapshot_json={
                "proposerId": str(proposer_id) if proposer_id else None,
                "memberId": str(member_id) if member_id else None,
                "productVersionId": str(product_version_id),
                "planId": str(plan_id),
                "effectiveDate": effective_date.isoformat(),
                "context": context,
            },
            evidence_json=[
                {"code": m.code, "severity": m.severity, "message": m.message} for m in messages
            ],
            correlation_id=correlation_id,
        )
        return evaluation
