"""Pure evaluation logic for Q360-S3-03, driven entirely by ART-008's Rule
Matrix ("Rule Matrix" sheet, rules ELIG-001..ELIG-010) — see
OPEN_DECISIONS.md#S03-ELIGIBILITY-001 for exactly which rules are final
(status PUBLISHED-CANDIDATE, no open parameter) versus provisional (status
DRAFT, thresholds/criteria unresolved per OD-004).

No business threshold (a minimum age, an allowed relationship list, a
referral condition) is hardcoded here — they are all read from
`EligibilityRuleConfig`, itself parsed from a tenant's published
`RuleVersion.artifact_ref` (rule_domain=ELIGIBILITY). An unconfigured
threshold simply never fires (its rule is a no-op), rather than defaulting
to some invented number.
"""
from __future__ import annotations

import dataclasses
import datetime
from typing import Any

from apps.eligibility.domain.enums import EligibilityDecision
from apps.eligibility.domain.messages_pt import friendly_text

from django.utils import timezone



@dataclasses.dataclass(frozen=True, slots=True)
class EligibilityMessage:
    code: str
    severity: str  # INFO | WARNING | ERROR (ART-006 EligibilityResponse.messages[].severity)
    message: str


@dataclasses.dataclass(frozen=True, slots=True)
class Criterion:
    """One entry of `referralCriteria`/`warningCriteria`. All provided
    fields must match (AND) for this entry to match; a list of entries is
    OR'd. This shape is NOT sourced from any approved document — ART-008
    explicitly says "No medical criteria invented in V1" for the rules that
    use it (ELIG-008/009) — it is a deliberately minimal, generic
    placeholder mechanism so the engine and its API are real and testable
    while Actuarial/Product define actual criteria. See
    OPEN_DECISIONS.md#S03-ELIGIBILITY-001.
    """

    relationship_codes: frozenset[str] | None = None
    min_age: int | None = None
    max_age: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Criterion":
        codes = raw.get("relationshipCodes")
        return cls(
            relationship_codes=frozenset(codes) if codes else None,
            min_age=raw.get("minAge"),
            max_age=raw.get("maxAge"),
        )

    def matches(self, *, age: int | None, relationship_code: str) -> bool:
        if self.relationship_codes is not None and relationship_code not in self.relationship_codes:
            return False
        if self.min_age is not None and (age is None or age < self.min_age):
            return False
        if self.max_age is not None and (age is None or age > self.max_age):
            return False
        return self.relationship_codes is not None or self.min_age is not None or self.max_age is not None


@dataclasses.dataclass(frozen=True, slots=True)
class CategoryRule:
    """One `categoryRules[<category>]` entry (MOTOR_ELEGIBILIDADE.md
    secção 3), already merged with any applicable `corporateOverrides` by
    `EligibilityRuleConfig.category_rule_for`. Fields not relevant to a
    given `RelationshipCategory` are simply left at their default and
    never read for that category."""

    max_age_without_proof: int | None = None
    max_age_with_proof: int | None = None
    proof_document_type: str | None = None
    proof_issuer_authority: str | None = None
    requires_union_proof_for: frozenset[str] | None = None
    requires_cohabitation_or_financial_dependency: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CategoryRule":
        union_for = raw.get("requiresUnionProofFor")
        return cls(
            max_age_without_proof=raw.get("maxAgeWithoutProof"),
            max_age_with_proof=raw.get("maxAgeWithProof"),
            proof_document_type=raw.get("proofDocumentType"),
            proof_issuer_authority=raw.get("proofIssuerAuthority"),
            requires_union_proof_for=frozenset(union_for) if union_for else None,
            requires_cohabitation_or_financial_dependency=bool(
                raw.get("requiresCohabitationOrFinancialDependency", False)
            ),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class WaitingPeriodConfig:
    """`waitingPeriod` (MOTOR_ELEGIBILIDADE.md secção 3). Informational
    only in Fase A — it never gates the eligibility decision, it is
    attached as an INFO message alongside a non-blocking outcome."""

    default_days: int = 0
    default_days_by_benefit_category: dict[str, int] = dataclasses.field(default_factory=dict)
    waived_on_verified_portability: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WaitingPeriodConfig":
        return cls(
            default_days=raw.get("defaultDays") or 0,
            default_days_by_benefit_category=dict(raw.get("defaultDaysByBenefitCategory") or {}),
            waived_on_verified_portability=bool(raw.get("waivedOnVerifiedPortability", False)),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class PreExistingConditionPolicy:
    """`preExistingConditionPolicy` (MOTOR_ELEGIBILIDADE.md secção 3).
    `mode="LOADING"` is the only mode implemented as a real premium effect
    here (see pricing); `mode="PENDING_MEDICAL_BOARD"` only produces a
    decision, never a percentage. There is deliberately no third mode that
    rejects definitively (design doc secção 1)."""

    mode: str = "LOADING"
    loading_percentage: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PreExistingConditionPolicy":
        return cls(mode=raw.get("mode", "LOADING"), loading_percentage=raw.get("loadingPercentage"))


@dataclasses.dataclass(frozen=True, slots=True)
class EligibilityRuleConfig:
    """Parsed `RuleVersion.artifact_ref` (artifact_type=JSON) for a
    published rule_domain=ELIGIBILITY version."""

    min_entry_age: int | None = None
    max_entry_age: int | None = None
    allowed_relationship_codes: frozenset[str] | None = None
    referral_criteria: tuple[Criterion, ...] = ()
    warning_criteria: tuple[Criterion, ...] = ()
    # MOTOR_ELEGIBILIDADE.md Fase A additions below. `category_rules` and
    # `corporate_overrides` are kept as raw dicts (not pre-parsed into
    # `CategoryRule`) because a corporate override only replaces the keys
    # actually present in its JSON — merging must happen on the raw dicts
    # before `CategoryRule.from_dict` runs, or "field absent" and "field
    # explicitly cleared" become indistinguishable. See `category_rule_for`.
    category_rules: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    corporate_overrides: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    waiting_period: WaitingPeriodConfig | None = None
    pre_existing_condition_policy: PreExistingConditionPolicy | None = None

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "EligibilityRuleConfig":
        codes = raw.get("allowedRelationshipCodes")
        waiting_period_raw = raw.get("waitingPeriod")
        pre_existing_raw = raw.get("preExistingConditionPolicy")
        return cls(
            min_entry_age=raw.get("minEntryAge"),
            max_entry_age=raw.get("maxEntryAge"),
            allowed_relationship_codes=frozenset(codes) if codes else None,
            referral_criteria=tuple(Criterion.from_dict(c) for c in raw.get("referralCriteria", [])),
            warning_criteria=tuple(Criterion.from_dict(c) for c in raw.get("warningCriteria", [])),
            category_rules=dict(raw.get("categoryRules") or {}),
            corporate_overrides=dict(raw.get("corporateOverrides") or {}),
            waiting_period=WaitingPeriodConfig.from_dict(waiting_period_raw) if waiting_period_raw else None,
            pre_existing_condition_policy=(
                PreExistingConditionPolicy.from_dict(pre_existing_raw) if pre_existing_raw else None
            ),
        )

    def category_rule_for(self, category: str | None, *, organisation_proposer_id: str | None) -> CategoryRule | None:
        """Merges the general `categoryRules[category]` with the
        `corporateOverrides[organisation_proposer_id].categoryRules[category]`
        entry, if any — any field present in the override replaces the
        general value, per MOTOR_ELEGIBILIDADE.md secção 3."""
        if category is None:
            return None
        general = self.category_rules.get(category)
        merged: dict[str, Any] = dict(general) if general else {}
        if organisation_proposer_id:
            override = self.corporate_overrides.get(organisation_proposer_id, {}).get("categoryRules", {})
            category_override = override.get(category)
            if category_override:
                merged.update(category_override)
        if not merged:
            return None
        return CategoryRule.from_dict(merged)


def _age_on(date_of_birth: datetime.date) -> int:
    today = timezone.localdate()

    years = today.year - date_of_birth.year

    if (today.month, today.day) < (
        date_of_birth.month,
        date_of_birth.day,
    ):
        years -= 1

    return years


@dataclasses.dataclass(frozen=True, slots=True)
class AngolaEvidence:
    """Evidence flags for the Fase A category-rule checks. These are
    supplied by the caller (via the eligibility request's existing
    `context` payload — see `EvaluateEligibilityUseCase`) and never looked
    up or inferred here: *where* a document is verified/stored is Fase B
    of MOTOR_ELEGIBILIDADE.md, still open. This dataclass only lets the
    pure `evaluate()` function branch on whatever boolean the caller
    asserts, without depending on that open decision."""

    has_enrollment_certificate: bool = False
    union_bond_type: str | None = None
    has_union_homologation_document: bool = False
    has_cohabitation_or_financial_dependency_proof: bool = False
    has_pre_existing_condition: bool = False
    previous_policy_number: str | None = None
    previous_policy_continuous: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "AngolaEvidence":
        raw = raw or {}
        return cls(
            has_enrollment_certificate=bool(raw.get("hasEnrollmentCertificate", False)),
            union_bond_type=raw.get("unionBondType"),
            has_union_homologation_document=bool(raw.get("hasUnionHomologationDocument", False)),
            has_cohabitation_or_financial_dependency_proof=bool(
                raw.get("hasCohabitationOrFinancialDependencyProof", False)
            ),
            has_pre_existing_condition=bool(raw.get("hasPreExistingCondition", False)),
            previous_policy_number=raw.get("previousPolicyNumber"),
            previous_policy_continuous=bool(raw.get("previousPolicyContinuous", False)),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class EvaluationInput:
    member_id: str | None
    relationship_code: str | None
    date_of_birth: datetime.date | None
    plan_id: str | None
    effective_date: datetime.date
    # MOTOR_ELEGIBILIDADE.md Fase A additions — all optional so existing
    # callers/tests that never set them keep exercising ELIG-001..010
    # exactly as before.
    relationship_category: str | None = None
    organisation_proposer_id: str | None = None
    angola_evidence: AngolaEvidence | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class PlanFacts:
    is_active: bool


@dataclasses.dataclass(frozen=True, slots=True)
class LegalAgeLimits:
    """Limites da camada geral do fornecedor: a maioridade (lei) e o teto de
    idade de um filho com prova de estudos. Prevalecem sobre a configuração
    do tenant, mesmo numa versão de regras publicada antes de mudarem."""

    age_of_majority: int | None = None
    max_age_with_proof: int | None = None


def _cap(value: int | None, limit: int | None) -> int | None:
    if value is None or limit is None:
        return value
    return min(value, limit)


def _evaluate_category_rules(
    *, data: EvaluationInput, age: int | None, config: EligibilityRuleConfig,
    legal: LegalAgeLimits | None = None,
) -> tuple[EligibilityDecision, list[EligibilityMessage]] | None:
    """MOTOR_ELEGIBILIDADE.md secção 1, "MÓDULO DE REGRAS DINÂMICAS" block
    (CHILD/SPOUSE/ASCENDANT). Returns None to mean "no verdict, continue
    evaluating" — mirrors the pseudocode's CONTINUA. Compliance and
    group-policy/payroll checks from the same pseudocode are deliberately
    NOT implemented here — MOTOR_ELEGIBILIDADE.md assigns them to Fase C
    (no real NIF/payroll integration exists; DOC-000's rule against
    inventing a fake integration applies)."""
    rule = config.category_rule_for(data.relationship_category, organisation_proposer_id=data.organisation_proposer_id)
    if rule is None:
        return None
    if legal is not None:
        rule = dataclasses.replace(
            rule,
            max_age_without_proof=_cap(rule.max_age_without_proof, legal.age_of_majority),
            max_age_with_proof=_cap(rule.max_age_with_proof, legal.max_age_with_proof),
        )
    evidence = data.angola_evidence or AngolaEvidence()

    if data.relationship_category == "CHILD":
        if age is None:
            return None
        if rule.max_age_without_proof is not None and age <= rule.max_age_without_proof:
            return None
        if rule.max_age_with_proof is not None and age <= rule.max_age_with_proof:
            if evidence.has_enrollment_certificate:
                return None
            severity, message = friendly_text("FALTA_CERTIFICADO_MATRICULA", limite=rule.max_age_without_proof)
            return EligibilityDecision.PENDING_DOCUMENT, [
                EligibilityMessage("FALTA_CERTIFICADO_MATRICULA", severity, message)
            ]
        if rule.max_age_without_proof is not None or rule.max_age_with_proof is not None:
            limit = rule.max_age_with_proof if rule.max_age_with_proof is not None else rule.max_age_without_proof
            severity, message = friendly_text("IDADE_ACIMA_LIMITE_DEPENDENTE", limite=limit)
            return EligibilityDecision.HARD_STOP, [
                EligibilityMessage("IDADE_ACIMA_LIMITE_DEPENDENTE", severity, message)
            ]
        return None

    if data.relationship_category == "SPOUSE":
        if (
            rule.requires_union_proof_for is not None
            and evidence.union_bond_type in rule.requires_union_proof_for
            and not evidence.has_union_homologation_document
        ):
            severity, message = friendly_text("FALTA_HOMOLOGACAO_UNIAO_FACTO")
            return EligibilityDecision.PENDING_DOCUMENT, [
                EligibilityMessage("FALTA_HOMOLOGACAO_UNIAO_FACTO", severity, message)
            ]
        return None

    if data.relationship_category == "ASCENDANT":
        if rule.requires_cohabitation_or_financial_dependency and not (
            evidence.has_cohabitation_or_financial_dependency_proof
        ):
            severity, message = friendly_text("FALTA_PROVA_DEPENDENCIA_ASCENDENTE")
            return EligibilityDecision.PENDING_DOCUMENT, [
                EligibilityMessage("FALTA_PROVA_DEPENDENCIA_ASCENDENTE", severity, message)
            ]
        return None

    return None


def _evaluate_pre_existing_condition(
    *, data: EvaluationInput, config: EligibilityRuleConfig
) -> tuple[EligibilityDecision, list[EligibilityMessage]] | None:
    """MOTOR_ELEGIBILIDADE.md secção 1, "PREEXISTÊNCIAS" block. Never a
    definitive rejection — only LOADING (premium acréscimo) or
    PENDING_MEDICAL_BOARD, per the design doc's explicit "nunca existe um
    terceiro ramo que rejeite definitivamente aqui"."""
    evidence = data.angola_evidence or AngolaEvidence()
    policy = config.pre_existing_condition_policy
    if not evidence.has_pre_existing_condition or policy is None:
        return None
    if policy.mode == "PENDING_MEDICAL_BOARD":
        severity, message = friendly_text("PENDENTE_JUNTA_MEDICA")
        return EligibilityDecision.PENDING_MEDICAL_BOARD, [
            EligibilityMessage("PENDENTE_JUNTA_MEDICA", severity, message)
        ]
    severity, message = friendly_text("ELIGIBLE_COM_AGRAVAMENTO", percentual=policy.loading_percentage or "0")
    return EligibilityDecision.ELIGIBLE_WITH_LOADING, [
        EligibilityMessage("ELIGIBLE_COM_AGRAVAMENTO", severity, message)
    ]


def _waiting_period_message(*, data: EvaluationInput, config: EligibilityRuleConfig) -> EligibilityMessage | None:
    """Informational only (never gates a decision) — attached to a
    non-blocking outcome so the caller/frontend has the carência figure
    without a second round-trip. None if no `waitingPeriod` is configured."""
    wp = config.waiting_period
    if wp is None:
        return None
    evidence = data.angola_evidence or AngolaEvidence()
    waived = wp.waived_on_verified_portability and bool(evidence.previous_policy_number) and evidence.previous_policy_continuous
    days = 0 if waived else wp.default_days
    return EligibilityMessage("ELIG-WAITING-PERIOD", "INFO", f"Período de carência: {days} dia(s).")


def evaluate(
    *,
    data: EvaluationInput,
    plan: PlanFacts | None,
    config: EligibilityRuleConfig | None,
    legal: LegalAgeLimits | None = None,
) -> tuple[EligibilityDecision, list[EligibilityMessage]]:
    """Pure function: same inputs always produce the same decision (DOC-004
    s9/DOC-000 P-02 determinism). Rule IDs referenced in comments are
    ART-008 Rule Matrix rows.

    DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26): ELIG-006
    ("product version not effective on quote date") is retired along with
    ProductVersion itself — a Plan has no [effectiveFrom, effectiveTo)
    range of its own, only a commercializable/not `status`, so this folds
    into ELIG-007 below (a Plan is either usable for new business or it
    isn't; there is no separate date-range check any more).
    """
    # ELIG-001 — Completeness (PUBLISHED-CANDIDATE, no open parameter).
    if not (data.member_id and data.plan_id and data.effective_date):
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("VALIDATION-400", "ERROR", "Faltam dados obrigatórios para avaliar a elegibilidade.")
        ]

    # Referenced entity must actually exist — not itself an ART-008 rule
    # (which assumes it resolves), but a precondition for evaluating
    # ELIG-007 at all.
    if plan is None:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("ELIG-REFERENCE-NOT-FOUND", "ERROR", "O plano indicado não existe.")
        ]

    # ELIG-007 — Plan inactive.
    if not plan.is_active:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("ELIG-PLAN-INACTIVE", "ERROR", "O plano escolhido não está ativo.")
        ]

    # ELIG-010 — No applicable rule version: fail closed (DOC-004 s9:
    # "CONFIG_ERROR nunca pode ser convertido silenciosamente em ELIGIBLE").
    if config is None:
        return EligibilityDecision.CONFIG_ERROR, [
            EligibilityMessage("ELIG-RULE-MISSING", "ERROR", "Não há regras de elegibilidade publicadas para este plano.")
        ]

    age: int | None = None
    if data.date_of_birth is not None:
        age = _age_on(data.date_of_birth)
    age_rule_configured = config.min_entry_age is not None or config.max_entry_age is not None
    # ELIG-002 — Age can be calculated (only relevant when an age rule is
    # actually configured; an unconfigured threshold must not force every
    # member to supply a date of birth).
    if age_rule_configured and age is None:
        return EligibilityDecision.CONFIG_ERROR, [
            EligibilityMessage(
                "PRICING-CONFIG", "ERROR", "Date of birth unavailable for age-based rule"
            )
        ]

    # ELIG-003 — Age below configured minimum.
    if config.min_entry_age is not None and age is not None and age < config.min_entry_age:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("ELIG-AGE-MIN", "ERROR", "A pessoa ainda não tem a idade mínima de adesão.")
        ]
    # ELIG-004 — Age above configured maximum.
    if config.max_entry_age is not None and age is not None and age > config.max_entry_age:
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage("ELIG-AGE-MAX", "ERROR", "A pessoa ultrapassa a idade máxima de adesão.")
        ]

    # ELIG-005 — Relationship not allowed by plan.
    if (
        config.allowed_relationship_codes is not None
        and data.relationship_code not in config.allowed_relationship_codes
    ):
        return EligibilityDecision.HARD_STOP, [
            EligibilityMessage(
                "ELIG-RELATIONSHIP", "ERROR", "Relationship not eligible for selected plan"
            )
        ]

    relationship_code = data.relationship_code or ""

    # --- Angola dynamic rules (MOTOR_ELEGIBILIDADE.md, Fase A) ---
    # Runs after ELIG-005 (relationship allowed) and before ELIG-008/009
    # (generic referral/warning), exactly as the design doc's decision
    # tree orders it.
    category_result = _evaluate_category_rules(data=data, age=age, config=config, legal=legal)
    if category_result is not None:
        return category_result

    pre_existing_result = _evaluate_pre_existing_condition(data=data, config=config)
    if pre_existing_result is not None:
        pe_decision, pe_messages = pre_existing_result
        wp_message = _waiting_period_message(data=data, config=config)
        if wp_message is not None:
            pe_messages = [*pe_messages, wp_message]
        return pe_decision, pe_messages

    # ELIG-008 — Configured referral condition matched.
    if any(c.matches(age=age, relationship_code=relationship_code) for c in config.referral_criteria):
        return EligibilityDecision.REFERRAL, [
            EligibilityMessage("ELIG-REFERRAL", "WARNING", "É necessária análise manual da subscrição.")
        ]

    # ELIG-009 — Configured warning matched.
    if any(c.matches(age=age, relationship_code=relationship_code) for c in config.warning_criteria):
        return EligibilityDecision.WARNING, [
            EligibilityMessage(
                "ELIG-WARNING", "WARNING", "Eligibility warning requires acknowledgement"
            )
        ]

    eligible_messages = [
        EligibilityMessage("ELIG-OK", "INFO", "Membro elegível segundo as regras aplicáveis."),
        EligibilityMessage("ELIG-PLAN-ACTIVE", "INFO", "O plano está ativo."),
    ]

    if age is not None and age_rule_configured:
        age_limits: list[str] = []
        if config.min_entry_age is not None:
            age_limits.append(f"mínimo {config.min_entry_age}")
        if config.max_entry_age is not None:
            age_limits.append(f"máximo {config.max_entry_age}")
        eligible_messages.append(
            EligibilityMessage(
                "ELIG-AGE-WITHIN-RANGE",
                "INFO",
                f"Idade de {age} anos dentro dos limites de entrada configurados ({' e '.join(age_limits)} anos).",
            )
        )

    if config.allowed_relationship_codes is not None:
        eligible_messages.append(
            EligibilityMessage(
                "ELIG-RELATIONSHIP-ALLOWED",
                "INFO",
                f"A relação familiar ({data.relationship_code or 'não informada'}) está permitida para o plano.",
            )
        )

    category_rule = config.category_rule_for(
        data.relationship_category,
        organisation_proposer_id=data.organisation_proposer_id,
    )
    category_evidence = data.angola_evidence or AngolaEvidence()
    if category_rule and data.relationship_category == "CHILD" and age is not None:
        if category_rule.max_age_without_proof is not None and age <= category_rule.max_age_without_proof:
            eligible_messages.append(
                EligibilityMessage(
                    "ELIG-CHILD-AGE",
                    "INFO",
                    f"A idade cumpre o limite de {category_rule.max_age_without_proof} anos para filhos sem comprovativo escolar.",
                )
            )
        elif (
            category_rule.max_age_with_proof is not None
            and age <= category_rule.max_age_with_proof
            and category_evidence.has_enrollment_certificate
        ):
            eligible_messages.append(
                EligibilityMessage(
                    "ELIG-CHILD-ENROLLMENT-PROOF",
                    "INFO",
                    "A idade está dentro do limite alargado e foi indicado comprovativo de matrícula.",
                )
            )
    elif (
        category_rule
        and data.relationship_category == "SPOUSE"
        and category_rule.requires_union_proof_for
        and category_evidence.union_bond_type in category_rule.requires_union_proof_for
        and category_evidence.has_union_homologation_document
    ):
        eligible_messages.append(
            EligibilityMessage(
                "ELIG-UNION-PROOF",
                "INFO",
                "O comprovativo de homologação da união exigido para esta relação foi indicado.",
            )
        )
    elif (
        category_rule
        and data.relationship_category == "ASCENDANT"
        and category_rule.requires_cohabitation_or_financial_dependency
        and category_evidence.has_cohabitation_or_financial_dependency_proof
    ):
        eligible_messages.append(
            EligibilityMessage(
                "ELIG-ASCENDANT-DEPENDENCY-PROOF",
                "INFO",
                "Foi indicado comprovativo de coabitação ou dependência financeira exigido para ascendentes.",
            )
        )

    wp_message = _waiting_period_message(data=data, config=config)
    if wp_message is not None:
        eligible_messages.append(wp_message)
    return EligibilityDecision.ELIGIBLE, eligible_messages
