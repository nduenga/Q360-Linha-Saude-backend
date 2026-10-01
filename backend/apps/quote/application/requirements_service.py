"""Requisitos e alertas de subscrição de uma cotação (PDF "Notas de
subscrição" e regras de Individual/Familiar e Grupo).

`evaluate_requirements(quote)` junta, por cotação e por pessoa:

  ERROS (bloqueiam o envio para revisão):
    - Grupo abaixo da dimensão mínima (abaixo disso, produto individual);
    - idade fora dos limites de **entrada** do plano e, na renovação, acima
      do limite de **permanência** (PDF: entrada até 60–65, renovação até
      70–75);
    - agregado: cônjuge não permitido, filho acima da idade limite (25).
  AVISOS / INFORMAÇÃO:
    - questionário clínico (obrigatório no individual; no grupo, dispensado
      com adesão obrigatória acima de ~20 pessoas);
    - exames médicos acima de uma idade (ex. 55) ou de um capital;
    - cobertura geográfica da rede (Luanda vs províncias);
    - pré-autorização (internamentos, exames de alto custo, cirurgias
      programadas, evacuação), destinos/moeda/risco cambial da evacuação;
    - sinistralidade dos últimos 3 anos na transferência de outra seguradora;
    - rever capitais e tabelas na renovação (inflação médica);
    - carências aplicáveis por cobertura e exclusões habituais;
    - participação nos resultados do grupo.

Só avalia o que o plano configurou (`plan.settings_json`): um plano sem
definições não produz erros — nada do que existia antes passa a falhar.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from apps.client.infrastructure.models import RelationshipCode
from apps.foundation.domain.problem import DomainProblem
from apps.pricing.application.plan_dimensions import main_capital, resolve_plan_pricing_context
from apps.product.domain.market_catalog import STANDARD_EXCLUSIONS
from apps.product.domain.plan_settings import validate_plan_settings
from apps.quote.infrastructure.models import Quote

_COUNTED = ("INCLUDED", "REFERRAL")
_PRIOR_LABELS = (
    ("internments", "internamentos"),
    ("highCostExams", "exames de alto custo"),
    ("scheduledSurgeries", "cirurgias programadas"),
)


class QuoteRequirementsError(DomainProblem):
    """The quote does not satisfy a blocking underwriting rule."""

    http_status = 400
    problem_code = "VALIDATION-400"


def _age_on(date_of_birth: datetime.date | None, on: datetime.date) -> int | None:
    if date_of_birth is None:
        return None
    years = on.year - date_of_birth.year
    if (on.month, on.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


def _item(severity: str, code: str, message: str, *, member_id: str | None = None, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message, "scope": "MEMBER" if member_id else "QUOTE"}
    if member_id:
        item["memberId"] = member_id
    item.update(extra)
    return item


def evaluate_requirements(quote: Quote, *, claims_months_available: int | None = None) -> dict[str, Any]:
    from apps.claims.application.summary_service import history_months

    if claims_months_available is None:
        claims_months_available = history_months(proposer_id=quote.proposer_id)
    plan = quote.plan
    settings = plan.settings_json or {}
    segment = settings.get("segment")
    group = settings.get("group") or {}
    questionnaire = settings.get("clinicalQuestionnaire") or {}
    household = settings.get("household") or {}
    effective = quote.effective_date
    is_renewal = quote.quote_type == "RENEWAL"

    try:
        _, plan_warnings = validate_plan_settings(settings)
    except DomainProblem:
        plan_warnings = []

    quote_members = list(quote.members.select_related("member").order_by("created_at", "id"))
    counted = [qm for qm in quote_members if qm.status in _COUNTED]
    try:
        plan_context = resolve_plan_pricing_context(plan=plan, selection=quote.selection_json)
        coverages = [c for c in plan_context.coverages if c["contracted"]]
    except DomainProblem:
        coverages = []
    categories = {rc.code: rc.category for rc in RelationshipCode.objects.all()}

    items: list[dict[str, Any]] = []
    members_report: dict[str, Any] = {}

    # ------------------------------------------------------------ quote level
    if segment == "GROUP":
        minimum = group.get("minInsured")
        if minimum is not None and len(counted) < int(minimum):
            items.append(
                _item(
                    "ERROR",
                    "GROUP_MIN_SIZE",
                    f"O grupo tem {len(counted)} pessoa(s) segura(s); a dimensão mínima é {minimum}. "
                    "Abaixo disso, deve usar-se o produto individual.",
                    insured=len(counted),
                    minimum=int(minimum),
                )
            )
        if group.get("profitSharing"):
            items.append(
                _item(
                    "INFO",
                    "PROFIT_SHARING",
                    f"Participação nos resultados: devolução de parte do prémio se a sinistralidade ficar abaixo de "
                    f"{group['profitSharing'].get('lossRatioThresholdPct')}%.",
                    lossRatioThresholdPct=group["profitSharing"].get("lossRatioThresholdPct"),
                )
            )
        if group.get("premiumBasis") == "EXPERIENCE" and claims_months_available is not None and claims_months_available < 12:
            items.append(
                _item("WARNING", "EXPERIENCE_RATING_NEEDS_CLAIMS", "Prémio por experiência: faltam dados de sinistralidade do grupo.")
            )
        if group.get("monthlyInclusionsExclusions"):
            items.append(_item("INFO", "MONTHLY_MOVEMENTS", "Inclusões e exclusões mensais; acerto de prémio no fim da anuidade."))
        items.append(
            _item(
                "INFO",
                "CLAIMS_HISTORY_ON_TRANSFER",
                "Em transferência de outra seguradora, pedir a sinistralidade dos últimos 3 anos.",
                monthsAvailable=claims_months_available,
                satisfied=bool(claims_months_available and claims_months_available >= 36),
            )
        )

    for warning in plan_warnings:
        if warning["code"] in ("NETWORK_COVERAGE", "AGE_LIMITS_MISSING", "GROUP_SETTINGS_MISSING"):
            items.append(_item("WARNING", warning["code"], warning["message"]))

    prior = settings.get("priorAuthorization") or {}
    applies = [(key, label) for key, label in _PRIOR_LABELS if prior.get(key)]
    if applies:
        items.append(
            _item(
                "INFO",
                "PRIOR_AUTHORIZATION",
                "Pré-autorização obrigatória para: " + ", ".join(label for _, label in applies) + ".",
                appliesTo=[key for key, _ in applies],
            )
        )
    for coverage in coverages:
        config = coverage["configuration"]
        if coverage["code"] == "MEDICAL_EVACUATION":
            items.append(
                _item(
                    "INFO",
                    "EVACUATION_TERMS",
                    "Evacuação/tratamento no estrangeiro: aprovação prévia obrigatória; destinos "
                    f"{', '.join(config.get('destinations') or ['a definir'])}; moeda do capital {config.get('currency', 'AOA')}"
                    + (" (considerar o risco cambial)." if config.get("currency") == "USD" else "."),
                    destinations=config.get("destinations") or [],
                    currency=config.get("currency", "AOA"),
                    requiresPriorApproval=True,
                )
            )

    if is_renewal and (settings.get("capitalIndexation") or {}).get("reviewOnRenewal"):
        applied = (quote.renewal_json or {}).get("capitalIndexation", {}).get("applied")
        if not applied:
            items.append(
                _item(
                    "WARNING",
                    "CAPITAL_INDEXATION_PENDING",
                    "Renovação: rever capitais e tabelas face à inflação dos custos médicos.",
                )
            )

    # ------------------------------------------------------------- per member
    entry = settings.get("entryAge")
    permanence = (settings.get("permanenceAge") or {}).get("max")
    exam_age = questionnaire.get("medicalExamAboveAge")
    exam_capital = questionnaire.get("medicalExamAboveCapital")
    hospital = next((c for c in coverages if c["code"] == "HOSPITALIZATION"), None)
    hospital_capital = Decimal(main_capital(hospital["configuration"])) if hospital and main_capital(hospital["configuration"]) else None

    if segment == "INDIVIDUAL_FAMILY":
        questionnaire_required = questionnaire.get("required", True)
    elif segment == "GROUP":
        waived_above = group.get("questionnaireWaivedAboveInsured", 20)
        questionnaire_required = not (group.get("adhesion") == "MANDATORY" and len(counted) > int(waived_above))
    else:
        questionnaire_required = None

    for qm in quote_members:
        member = qm.member
        member_id = str(member.id)
        age = _age_on(member.date_of_birth, effective)
        category = categories.get(member.relationship_code)
        member_items: list[dict[str, Any]] = []

        if age is not None and entry and not is_renewal:
            low, high = entry.get("min", 0), entry.get("max")
            if (high is not None and age > high) or age < low:
                member_items.append(
                    _item("ERROR", "AGE_OUT_OF_ENTRY_RANGE", f"Idade {age} fora do intervalo de entrada do plano ({low}–{high}).", member_id=member_id, age=age)
                )
        if age is not None and is_renewal and permanence is not None and age > permanence:
            member_items.append(
                _item("ERROR", "AGE_ABOVE_PERMANENCE_LIMIT", f"Idade {age} acima do limite de permanência/renovação do plano ({permanence}).", member_id=member_id, age=age)
            )
        if household:
            if category == "SPOUSE" and household.get("spouse") is False:
                member_items.append(_item("ERROR", "SPOUSE_NOT_ALLOWED", "O plano não inclui cônjuge/unido de facto.", member_id=member_id))
            max_child = household.get("dependentChildMaxAge")
            if category == "CHILD" and age is not None and max_child is not None and age > max_child:
                member_items.append(
                    _item("ERROR", "CHILD_AGE_LIMIT", f"Filho(a) com {age} anos: o limite para filhos a cargo é {max_child}.", member_id=member_id, age=age)
                )
            student_age = household.get("studentsOnlyAboveAge")
            if category == "CHILD" and age is not None and student_age is not None and age > student_age:
                member_items.append(
                    _item("WARNING", "CHILD_STUDENT_PROOF", "Filho(a) acima da idade limite sem estudos: exige comprovativo de estudante.", member_id=member_id, age=age)
                )

        exam_reasons = []
        if age is not None and exam_age is not None and age >= exam_age:
            exam_reasons.append(f"idade {age} ≥ {exam_age}")
        if hospital_capital is not None and exam_capital is not None and hospital_capital >= Decimal(str(exam_capital)):
            exam_reasons.append(f"capital {hospital_capital} ≥ {exam_capital}")
        if exam_reasons:
            member_items.append(_item("WARNING", "MEDICAL_EXAM_REQUIRED", "Exames médicos exigidos: " + "; ".join(exam_reasons) + ".", member_id=member_id))
        if questionnaire_required:
            member_items.append(_item("WARNING", "CLINICAL_QUESTIONNAIRE_REQUIRED", "Questionário clínico obrigatório.", member_id=member_id))
        if qm.pre_existing_json:
            member_items.append(
                _item("INFO", "PRE_EXISTING_DECISION", f"Preexistência: {qm.pre_existing_json.get('mode')}.", member_id=member_id, decision=qm.pre_existing_json)
            )

        items.extend(member_items)
        members_report[member_id] = {
            "ageAtEffectiveDate": age,
            "relationshipCategory": category,
            "clinicalQuestionnaireRequired": bool(questionnaire_required),
            "medicalExamRequired": bool(exam_reasons),
            "blocking": any(i["severity"] == "ERROR" for i in member_items),
        }

    # -------------------------------------------- waiting periods & exclusions
    individual = segment != "GROUP"
    waiting = []
    for coverage in coverages:
        days = coverage["configuration"].get("waitingDays") or {}
        key = "individual" if individual else "group"
        if days.get(key) is not None or days.get("scheduledSurgery") is not None:
            waiting.append(
                {
                    "coverage": coverage["code"],
                    "days": days.get(key),
                    "scheduledSurgeryDays": days.get("scheduledSurgery"),
                    "accidentWaived": days.get("accidentWaived", settings.get("waitingRules", {}).get("accidentWaived", True)),
                }
            )
    exclusions = [{"code": e["code"], "text": e["text"], "productDependent": bool(e.get("productDependent"))} for e in STANDARD_EXCLUSIONS]
    for coverage in coverages:
        for excluded in coverage["configuration"].get("excludedItems") or []:
            exclusions.append({"code": f"{coverage['code']}_EXCLUDED_ITEM", "text": f"{coverage['name']}: {excluded}", "productDependent": False})

    errors = [i for i in items if i["severity"] == "ERROR"]
    return {
        "quoteId": str(quote.id),
        "segment": segment,
        "blocking": bool(errors),
        "errors": errors,
        "warnings": [i for i in items if i["severity"] == "WARNING"],
        "info": [i for i in items if i["severity"] == "INFO"],
        "members": members_report,
        "waitingPeriods": waiting,
        "exclusions": exclusions,
    }


def enforce_requirements(quote: Quote) -> None:
    """Called before a quote is submitted for review: blocking underwriting
    rules (group minimum size, age limits, household rules) must hold."""
    result = evaluate_requirements(quote)
    if result["blocking"]:
        raise QuoteRequirementsError(
            "The quote does not satisfy the plan's underwriting rules: " + " | ".join(e["message"] for e in result["errors"])
        )
