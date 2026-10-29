"""Conteúdo estruturado da proposta (R8), em português, a partir da cotação
(ou de um cenário) e do plano configurado — tudo o que o PDF "Coberturas e
Capitais" manda dizer ao cliente: coberturas e capitais por forma de
garantia, participação na rede e no reembolso, carências, opção de
participação, exclusões, doenças preexistentes por pessoa, pré-autorização,
evacuação (destinos, moeda, risco cambial), idades de entrada/permanência,
regras de Grupo e o aviso de que os valores indicativos devem ser
confirmados nas Condições Gerais.

Não renderiza nada: devolve um dicionário que os renderizadores (HTML, PDF,
DOCX) percorrem e que fica guardado no snapshot do documento — assim o mesmo
conteúdo pode ser reproduzido (`retry`) sem recalcular.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from apps.client.infrastructure.models import RelationshipCode
from apps.pricing.application.plan_dimensions import resolve_plan_pricing_context
from apps.business_config.application.branding import branding_from
from apps.business_config.application.overlays import effective_exclusions, effective_plan_settings
from apps.business_config.application.readers import BusinessSnapshot
from apps.product.domain.market_catalog import STANDARD_EXCLUSIONS
from apps.quote.application import quote_service, requirements_service
from apps.quote.domain.proposal_template import DEFAULT_DISCLAIMER
from apps.quote.infrastructure.models import Quote, QuoteScenario

ACCESS_SYSTEM_TEXT = {
    "NETWORK": "Rede convencionada (pagamento direto ao prestador)",
    "REIMBURSEMENT": "Reembolso (livre escolha do médico ou clínica)",
    "MIXED": "Misto: rede em Angola; reembolso fora da rede ou no estrangeiro",
}
SEGMENT_TEXT = {"INDIVIDUAL_FAMILY": "Individual e Familiar", "GROUP": "Grupo (Empresas)"}
TIER_TEXT = {"BASE": "Base", "MEDIUM": "Médio", "SUPERIOR": "Superior", "CUSTOM": "À medida"}
BLOCK_TEXT = {"NETWORK": "Rede convencionada", "REIMBURSEMENT": "Reembolso"}
QUOTE_TYPE_TEXT = {"NEW": "Novo negócio", "RENEWAL": "Renovação"}
KIND_TEXT = {
    "ANNUAL_PER_PERSON": "Capital anual por pessoa",
    "HOUSEHOLD_SHARED": "Capital por agregado (partilhado)",
    "SUBLIMIT": "Sublimite",
    "PER_ACT_OR_DAY": "Limite por ato ou por dia",
    "QUANTITY": "Limite de quantidade",
    "COINSURANCE_PCT": "Comparticipação da seguradora",
    "FIXED_AMOUNT": "Capital fixo",
    "PER_EVENT": "Capital por evento",
    "BIENNIAL": "Capital por 2 anos",
    "PER_SERVICE": "Limite por serviço",
}
UNIT_TEXT = {"SESSION": "sessões", "DAY": "dias", "ACT": "atos"}
PRE_EXISTING_TEXT = {
    "TOTAL_EXCLUSION": "Exclusão total: a doença declarada ou conhecida não é coberta.",
    "SPECIFIC_EXCLUSION": "Exclusão específica: só a doença declarada fica excluída, o resto é coberto.",
    "ACCEPTED_WITH_WAITING": "Aceitação com carência: coberta após o período indicado.",
    "ACCEPTED_WITH_LOADING": "Aceitação com sobreprémio: coberta com agravamento do prémio.",
    "ACCEPTED_WITH_SUBLIMIT": "Aceitação com sublimite: coberta até um capital reduzido.",
    "FULL_ACCEPTANCE": "Aceitação integral: coberta como qualquer outra doença.",
}


def money(amount: Any, currency: str = "AOA") -> str:
    """Mesma regra de todo o produto (`shared.formatting.money`)."""
    from shared.formatting import money as format_money

    return format_money(amount, currency)


def _limit_text(limit: dict[str, Any], currency: str) -> str:
    kind = limit.get("kind")
    label = limit.get("label") or KIND_TEXT.get(kind, kind)
    if kind == "QUANTITY":
        return f"{label}: {limit.get('count')} {UNIT_TEXT.get(limit.get('unit'), 'atos')}"
    if kind == "COINSURANCE_PCT":
        return f"{label}: {limit.get('pct')}%"
    suffix = "/dia" if limit.get("unit") == "PER_DAY" else ""
    prefix = f"{KIND_TEXT.get(kind, kind)} — {label}" if limit.get("label") and kind in ("PER_EVENT",) else label
    return f"{prefix}: {money(limit['amount'], currency)}{suffix}"


def _participation_lines(participation: dict[str, Any], currency: str) -> list[str]:
    lines: list[str] = []
    for block in ("NETWORK", "REIMBURSEMENT"):
        spec = participation.get(block)
        if not spec:
            continue
        ptype = spec.get("type", "NONE")
        if ptype == "NONE":
            text = "sem participação do segurado"
        elif ptype == "COPAY_FIXED":
            text = f"copagamento de {money(spec['copayAmount'], currency)} por ato"
        else:
            insurer = Decimal(str(spec["insurerPct"]))
            text = f"a seguradora paga {insurer.normalize():f}% e o segurado {(Decimal(100) - insurer).normalize():f}%"
            if spec.get("insuredAnnualCap"):
                text += f" (teto anual a cargo do segurado: {money(spec['insuredAnnualCap'], currency)})"
        extras = []
        if spec.get("annualDeductible") and Decimal(str(spec["annualDeductible"])) > 0:
            extras.append(f"franquia anual de {money(spec['annualDeductible'], currency)}")
        if spec.get("perEventDeductible") and Decimal(str(spec["perEventDeductible"])) > 0:
            extras.append(f"franquia de {money(spec['perEventDeductible'], currency)} por evento")
        if extras:
            text += "; " + "; ".join(extras)
        lines.append(f"{BLOCK_TEXT[block]}: {text}")
    return lines


def _waiting_text(config: dict[str, Any], segment: str | None) -> str | None:
    days = config.get("waitingDays") or {}
    key = "group" if segment == "GROUP" else "individual"
    value = days.get(key)
    if value is None and days.get("scheduledSurgery") is None:
        return None
    parts = []
    if value is not None:
        parts.append("sem carência" if value == 0 else f"{value} dias")
    if days.get("scheduledSurgery") is not None:
        parts.append(f"cirurgias programadas: {days['scheduledSurgery']} dias")
    if days.get("accidentWaived"):
        parts.append("em acidente não há carência")
    return "; ".join(parts)


def _member_name(member) -> str:
    name = " ".join(part for part in (member.first_name, member.last_name) if part)
    return name or f"Pessoa segura {str(member.id)[:8]}"


def _age(date_of_birth: datetime.date | None, on: datetime.date) -> int | None:
    if date_of_birth is None:
        return None
    years = on.year - date_of_birth.year
    return years - ((on.month, on.day) < (date_of_birth.month, date_of_birth.day))


def _adjustment_text(spec: dict[str, Any], currency: str, members: dict[str, str]) -> str:
    kind, value = spec["kind"], spec["value"]
    base = {
        "SURCHARGE_PERCENT": f"Agravamento de {Decimal(str(value)).normalize():f}%",
        "DISCOUNT_PERCENT": f"Desconto de {Decimal(str(value)).normalize():f}%",
        "SURCHARGE_AMOUNT": f"Agravamento fixo de {money(value, currency)}",
        "DISCOUNT_AMOUNT": f"Desconto fixo de {money(value, currency)}",
    }[kind]
    if spec.get("scope") == "MEMBER" and spec.get("memberId") in members:
        base += f" ({members[spec['memberId']]})"
    return base


def build_content(
    *, quote: Quote, scenario: QuoteScenario | None, calculation: dict[str, Any], generated_on: datetime.date
) -> dict[str, Any]:
    """`calculation` is a rendered pricing response (`render_preview` /
    `scenario.result_json`): `totalAmount`, `currencyCode`, `components`."""
    plan = quote.plan
    snapshot = BusinessSnapshot.load(quote.reference_date).for_product(plan.product_id)
    settings = effective_plan_settings(plan, quote.reference_date, snapshot)
    segment = settings.get("segment")
    currency = calculation.get("currencyCode") or quote.currency_code or "AOA"

    selection = (scenario.parameters_json.get("selection") if scenario else quote.selection_json) or {}
    adjustments = scenario.parameters_json.get("adjustments", []) if scenario else [
        {k: v for k, v in item.items() if k != "id"}
        for item in quote_service.active_adjustments_for_context(quote)
    ]
    plan_context = resolve_plan_pricing_context(plan=plan, selection=selection, effective_date=quote.reference_date)

    quote_members = list(quote.members.select_related("member").order_by("created_at", "id"))
    names = {str(qm.member_id): _member_name(qm.member) for qm in quote_members}
    categories = {rc.code: rc.label for rc in RelationshipCode.objects.all()}
    requirements = requirements_service.evaluate_requirements(quote)

    # ---------------------------------------------------------- population
    population = []
    for qm in quote_members:
        member = qm.member
        info = requirements["members"].get(str(member.id), {})
        decision = qm.pre_existing_json or {}
        population.append(
            {
                "memberId": str(member.id),
                "name": names[str(member.id)],
                "relationship": categories.get(member.relationship_code, member.relationship_code),
                "age": _age(member.date_of_birth, quote.reference_date),
                "status": qm.status,
                "clinicalQuestionnaireRequired": info.get("clinicalQuestionnaireRequired", False),
                "medicalExamRequired": info.get("medicalExamRequired", False),
                "preExisting": (
                    {
                        "mode": decision.get("mode"),
                        "text": PRE_EXISTING_TEXT.get(decision.get("mode"), ""),
                        "condition": decision.get("condition"),
                        "waitingMonths": decision.get("waitingMonths"),
                        "loadingPct": decision.get("loadingPct"),
                        "sublimitAmount": money(decision["sublimitAmount"], currency) if decision.get("sublimitAmount") else None,
                    }
                    if decision
                    else None
                ),
            }
        )

    # ----------------------------------------------------------- coverages
    coverages = []
    for coverage in plan_context.coverages:
        config = coverage["configuration"]
        cov_currency = config.get("currency", "AOA")
        coverages.append(
            {
                "code": coverage["code"],
                "name": coverage["name"],
                "category": coverage["category"],
                "inclusion": coverage["inclusion"],
                "contracted": coverage["contracted"],
                "limits": [_limit_text(limit, cov_currency) for limit in config.get("limits", [])],
                "participation": _participation_lines(config.get("participation") or {}, cov_currency),
                "waiting": _waiting_text(config, segment),
                "requiresPriorApproval": bool(config.get("requiresPriorApproval")),
                "destinations": config.get("destinations") or [],
                "closedDiseaseList": config.get("closedDiseaseList") or [],
                "currency": cov_currency,
                "maxDaysPerYear": config.get("maxDaysPerYear"),
                "timeDeductibleDays": config.get("timeDeductibleDays"),
                "excludedItems": config.get("excludedItems") or [],
                "notes": config.get("notes"),
                "indicative": bool(config.get("indicative")),
            }
        )

    # ------------------------------------------------------------- premium
    by_member: dict[str, list[dict[str, Any]]] = {}
    quote_level: list[dict[str, Any]] = []
    for component in calculation.get("components", []):
        member_id = component.get("memberId")
        (by_member.setdefault(member_id, []) if member_id else quote_level).append(component)
    premium_members = []
    for qm in quote_members:
        lines = by_member.get(str(qm.member_id))
        if not lines:
            continue
        premium_members.append(
            {
                "memberId": str(qm.member_id),
                "name": names[str(qm.member_id)],
                "total": lines[-1]["resultAmount"],
                "lines": [
                    {
                        "code": c["code"],
                        "type": c["type"],
                        "factor": c.get("factorValue"),
                        "adjustment": c.get("adjustmentAmount"),
                        "result": c["resultAmount"],
                    }
                    for c in lines
                ],
            }
        )
    option = plan_context.participation_option
    option_detail = None
    if option is not None:
        definition = next((o for o in settings.get("participationOptions", []) if o["code"] == option.code), {})
        option_detail = {
            "code": option.code,
            "name": definition.get("name"),
            "annualDeductible": money(definition["annualDeductible"], currency) if definition.get("annualDeductible") is not None else None,
            "copayPerConsultation": money(definition["copayPerConsultation"], currency) if definition.get("copayPerConsultation") is not None else None,
            "reimbursementPct": definition.get("reimbursementPct"),
            "premiumAdjustmentPct": definition.get("premiumAdjustmentPct"),
            "hospitalOnly": bool(definition.get("hospitalOnly")),
        }

    # ---------------------------------------------------------- conditions
    group = settings.get("group") or {}
    conditions: list[str] = []
    prior = [item for item in requirements["info"] if item["code"] in ("PRIOR_AUTHORIZATION", "EVACUATION_TERMS")]
    conditions.extend(item["message"] for item in prior)
    if settings.get("entryAge") or settings.get("permanenceAge"):
        entry = (settings.get("entryAge") or {}).get("max")
        stay = (settings.get("permanenceAge") or {}).get("max")
        conditions.append(
            "Idade de entrada até " + (f"{entry} anos" if entry is not None else "—")
            + "; renovação até " + (f"{stay} anos" if stay is not None else "—") + "."
        )
    household = settings.get("household")
    if household:
        parts = ["cônjuge ou unido de facto" if household.get("spouse", True) else None]
        if household.get("dependentChildMaxAge"):
            parts.append(f"filhos até aos {household['dependentChildMaxAge']} anos" + (" se estudantes" if household.get("childrenMustBeStudents") else ""))
        conditions.append("Agregado familiar: " + ", ".join(p for p in parts if p) + ".")
    if quote.quote_type == "RENEWAL":
        conditions.append("Renovação: os capitais e tabelas são revistos face à inflação dos custos médicos.")
    if segment == "GROUP":
        if group.get("adhesion"):
            conditions.append("Adesão " + ("obrigatória" if group["adhesion"] == "MANDATORY" else "facultativa") + ".")
        if group.get("premiumPayer") == "COMPANY":
            conditions.append("O prémio é pago integralmente pela empresa.")
        elif group.get("premiumPayer") == "EMPLOYEE_COPAYS_FAMILY":
            conditions.append("A empresa paga o prémio dos trabalhadores; o prémio dos familiares é copago pelo trabalhador.")
        if group.get("monthlyInclusionsExclusions"):
            conditions.append("Inclusões e exclusões mensais, com acerto de prémio no fim da anuidade.")
        if group.get("profitSharing"):
            conditions.append(
                f"Participação nos resultados: devolução de parte do prémio se a sinistralidade ficar abaixo de "
                f"{group['profitSharing'].get('lossRatioThresholdPct')}%."
            )
        if group.get("includesRetirees"):
            conditions.append("Inclui reformados.")
        if group.get("continuityAfterLeaving"):
            conditions.append("Continuidade após saída da empresa: conversão para contrato individual sem novo questionário.")
    if (settings.get("network") or {}).get("regions"):
        regions = {"LUANDA": "Luanda", "PROVINCES": "províncias"}
        conditions.append("Rede convencionada em: " + ", ".join(regions[r] for r in settings["network"]["regions"]) + ".")
    conditions.append(
        "Não há regra de rateio: esgotado o capital anual, a seguradora deixa de pagar até à anuidade seguinte."
    )

    exclusions = [e["text"] for e in effective_exclusions(plan, STANDARD_EXCLUSIONS, quote.reference_date, snapshot)]
    for coverage in coverages:
        for item in coverage["excludedItems"]:
            exclusions.append(f"{coverage['name']}: {item}")

    waiting = [
        {"coverage": c["name"], "text": c["waiting"]} for c in coverages if c["contracted"] and c["waiting"]
    ]
    default_treatment = settings.get("preExistingTreatment") or {}
    indicative = bool(settings.get("indicative")) or any(c["indicative"] for c in coverages if c["contracted"])

    return {
        "meta": {
            "quoteId": str(quote.id),
            "quoteNumber": quote.quote_number,
            "quoteType": QUOTE_TYPE_TEXT.get(quote.quote_type, quote.quote_type),
            "quoteDate": quote.reference_date.isoformat(),
            "validUntil": quote.valid_until.isoformat() if quote.valid_until else None,
            "generatedOn": generated_on.isoformat(),
            "currency": currency,
            "scenario": {"id": str(scenario.id), "name": scenario.name} if scenario else None,
        },
        "client": {
            "name": quote.proposer.display_name,
            "nif": quote.proposer.nif or quote.proposer.registration_number,
            "email": quote.proposer.email,
            "phone": quote.proposer.phone,
        },
        "plan": {
            "product": plan.product.name,
            "name": plan.name,
            "segment": SEGMENT_TEXT.get(segment, segment),
            "tier": TIER_TEXT.get(settings.get("tier")),
            "category": settings.get("category"),
            "accessSystem": ACCESS_SYSTEM_TEXT.get(settings.get("accessSystem")),
        },
        "population": population,
        "coverages": coverages,
        "participationOption": option_detail,
        "premium": {
            "total": calculation["totalAmount"],
            "totalText": money(calculation["totalAmount"], currency),
            "currency": currency,
            "members": premium_members,
            "quoteLevel": [
                {"code": c["code"], "type": c["type"], "adjustment": c.get("adjustmentAmount"), "result": c["resultAmount"]}
                for c in quote_level
                if c["type"] != "TOTAL"
            ],
            "adjustments": [_adjustment_text(spec, currency, names) for spec in adjustments],
            "warnings": [w.get("message") for w in calculation.get("warnings", []) if w.get("message")],
        },
        "waiting": waiting,
        "preExisting": {
            "defaultTreatment": PRE_EXISTING_TEXT.get(default_treatment.get("mode")) if default_treatment else None,
            "decisions": [p for p in population if p["preExisting"]],
        },
        "exclusions": exclusions,
        "conditions": conditions,
        "businessTexts": [
            {"code": t.get("code"), "title": t.get("title"), "text": t.get("text")}
            for t in snapshot.rows("proposal.texts", "texts")
            if t.get("active") is not False and t.get("text")
        ],
        "requiredDocuments": [
            {"documentType": d.get("document_type"), "description": d.get("description")}
            for d in snapshot.rows("proposal.documents", "documents")
            if d.get("required")
        ],
        "branding": branding_from(snapshot),
        "disclaimer": DEFAULT_DISCLAIMER if indicative else None,
    }
