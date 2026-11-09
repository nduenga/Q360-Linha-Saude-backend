"""Comparador de planos (`GET /plans/compare`): matriz lado a lado de 2 a 4
planos, construída **só a partir do que já está configurado** —
`Plan.settings_json` (ver `apps.product.domain.plan_settings`) e
`PlanBenefit.configuration_json` (ver `apps.product.domain.coverage_config`).
Não há modelo próprio: o comparador é uma leitura.

Cada célula diz explicitamente o seu estado, porque «não existe» e «não sei»
não são a mesma coisa para quem decide:

  - `VALUE`              — há um valor (`value`, e `currency` quando é dinheiro);
  - `NOT_INCLUDED`       — o plano não oferece a cobertura;
  - `NOT_APPLICABLE`     — o atributo não faz sentido neste plano/cobertura
                           (p.ex. regras de grupo num plano individual, bloco
                           de reembolso num plano só de rede);
  - `NOT_INFORMED`       — o GTE não configurou o valor;
  - `SUBJECT_TO_ASSESSMENT` — depende de análise da seguradora (p.ex.
                           preexistentes com exclusão específica após análise).

Os valores monetários e percentagens seguem como texto decimal (regra ART-006)
e sem formatação: a formatação (Kz, separadores) é feita só no frontend.

Prémio: depende da composição (idades, sexo, parentesco), por isso só é
comparado quando o pedido traz `composition`. Cada plano é tarifado pelo
cálculo real de uma cotação de exemplo (`tariff_service.simulate_tariff`),
que cria proponente, pessoas e cotação temporários e reverte tudo: nada fica
gravado. Um plano que não se consegue tarifar (tarifa por publicar, pessoa
fora das idades...) não impede a comparação — a célula diz porquê.
"""
from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.application.overlays import effective_plan_settings
from apps.foundation.domain.problem import DomainProblem
from apps.product.application.plan_configuration_service import validate_plan
from apps.product.domain.enums import PlanStatus, ProductStatus
from apps.product.domain.market_catalog import GUARANTEE_FORMS
from apps.product.infrastructure.models import Plan, PlanBenefit

MIN_PLANS = 2
MAX_PLANS = 4

VALUE = "VALUE"
NOT_INCLUDED = "NOT_INCLUDED"
NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_INFORMED = "NOT_INFORMED"
SUBJECT_TO_ASSESSMENT = "SUBJECT_TO_ASSESSMENT"

_PRIMARY_KINDS = ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED", "BIENNIAL", "FIXED_AMOUNT")
_SUB_KINDS = ("SUBLIMIT", "PER_ACT_OR_DAY", "PER_SERVICE", "PER_EVENT")
_ACCESS_BLOCKS = {"NETWORK": ("NETWORK",), "REIMBURSEMENT": ("REIMBURSEMENT",), "MIXED": ("NETWORK", "REIMBURSEMENT")}
_ASSESSED_PRE_EXISTING = ("SPECIFIC_EXCLUSION", "ACCEPTED_WITH_LOADING")


class InvalidPlanComparisonError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class PlanComparisonNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


# ------------------------------------------------------------------ cells
def _value(value: Any, *, currency: str | None = None) -> dict[str, Any]:
    cell: dict[str, Any] = {"state": VALUE, "value": value}
    if currency:
        cell["currency"] = currency
    return cell


def _state(state: str) -> dict[str, Any]:
    return {"state": state, "value": None}


def _or_not_informed(value: Any, *, currency: str | None = None) -> dict[str, Any]:
    if value is None or value == "" or value == []:
        return _state(NOT_INFORMED)
    return _value(value, currency=currency)


def _row(key: str, label: str, cells: list[dict[str, Any]], unit: str | None = None) -> dict[str, Any]:
    comparable = [(c["state"], c.get("value"), c.get("currency")) for c in cells]
    row: dict[str, Any] = {
        "key": key,
        "label": label,
        "cells": cells,
        "different": any(item != comparable[0] for item in comparable[1:]),
    }
    if unit:
        row["unit"] = unit
    return row


def _section(key: str, label: str, rows: list[dict[str, Any]], *, kind: str = "PLAN", **extra: Any) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "kind": kind,
        **extra,
        "different": any(r["different"] for r in rows),
        "rows": rows,
    }


def _get(data: dict[str, Any] | None, *path: str) -> Any:
    current: Any = data or {}
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _decimal(raw: Any) -> Decimal | None:
    try:
        return Decimal(str(raw)) if raw is not None else None
    except InvalidOperation:
        return None


# ----------------------------------------------------------------- loading
def _parse_ids(raw_ids: list[str]) -> list[uuid.UUID]:
    parts = [p.strip() for raw in raw_ids for p in raw.split(",") if p.strip()]
    ids: list[uuid.UUID] = []
    for part in parts:
        try:
            plan_id = uuid.UUID(part)
        except ValueError:
            raise InvalidPlanComparisonError(f"planIds: '{part}' não é um identificador válido") from None
        if plan_id not in ids:
            ids.append(plan_id)
    if not MIN_PLANS <= len(ids) <= MAX_PLANS:
        raise InvalidPlanComparisonError(f"Escolha entre {MIN_PLANS} e {MAX_PLANS} planos diferentes para comparar")
    return ids


def _load(plan_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    plans = {p.id: p for p in Plan.objects.filter(id__in=plan_ids).select_related("product")}
    missing = [str(i) for i in plan_ids if i not in plans]
    if missing:
        raise PlanComparisonNotFoundError(f"Plano(s) não encontrado(s): {', '.join(missing)}")
    loaded = []
    for plan_id in plan_ids:
        plan = plans[plan_id]
        coverages = {
            pb.benefit.code: pb
            for pb in PlanBenefit.objects.filter(plan=plan).select_related("benefit").order_by("benefit__code")
        }
        loaded.append({"plan": plan, "settings": effective_plan_settings(plan), "coverages": coverages})
    return loaded


# ---------------------------------------------------------------- sections
def _header(item: dict[str, Any]) -> dict[str, Any]:
    plan, settings = item["plan"], item["settings"]
    return {
        "planId": str(plan.id),
        "planCode": plan.code,
        "planName": plan.name,
        "planStatus": plan.status,
        "productId": str(plan.product_id),
        "productCode": plan.product.code,
        "productName": plan.product.name,
        "productStatus": plan.product.status,
        "segment": settings.get("segment"),
        "tier": settings.get("tier"),
        "level": settings.get("level"),
        "currency": settings.get("currency") or "AOA",
    }


def _plan_rows(items: list[dict[str, Any]], spec: list[tuple]) -> list[dict[str, Any]]:
    """`spec`: (key, label, path, applies(settings) | None, unit | None)."""
    rows = []
    for key, label, path, applies, unit in spec:
        cells = []
        for item in items:
            settings = item["settings"]
            if applies is not None and not applies(settings):
                cells.append(_state(NOT_APPLICABLE))
            else:
                cells.append(_or_not_informed(_get(settings, *path)))
        rows.append(_row(key, label, cells, unit))
    return rows


def _is_individual(settings: dict[str, Any]) -> bool:
    return settings.get("segment") == "INDIVIDUAL_FAMILY"


def _is_group(settings: dict[str, Any]) -> bool:
    return settings.get("segment") == "GROUP"


def _uses_network(settings: dict[str, Any]) -> bool:
    return settings.get("accessSystem") in ("NETWORK", "MIXED")


def _identification(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        _row("product", "Produto", [_value(i["plan"].product.name) for i in items]),
        _row("planCode", "Código do plano", [_value(i["plan"].code) for i in items]),
        _row("planStatus", "Estado do plano", [_value(i["plan"].status) for i in items]),
        *_plan_rows(items, [
            ("segment", "Segmento", ("segment",), None, None),
            ("tier", "Escalão", ("tier",), None, None),
            ("level", "Nível na gama", ("level",), None, None),
            ("accessSystem", "Sistema de acesso", ("accessSystem",), None, None),
            ("costSharingModel", "Modelo de participação", ("costSharingModel",), None, None),
            ("currency", "Moeda do plano", ("currency",), None, None),
        ]),
        _row("noProRata", "Sem rateio", [_value(True) for _ in items]),
    ]
    return _section("identification", "Identificação e características", rows)


def _eligibility(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _plan_rows(items, [
        ("entryAgeMin", "Idade mínima de adesão", ("entryAge", "min"), None, "YEARS"),
        ("entryAgeMax", "Idade máxima de adesão", ("entryAge", "max"), None, "YEARS"),
        ("permanenceAgeMax", "Idade máxima de permanência", ("permanenceAge", "max"), None, "YEARS"),
        ("spouse", "Inclusão do cônjuge", ("household", "spouse"), _is_individual, None),
        ("dependentChildMaxAge", "Idade máxima dos filhos dependentes", ("household", "dependentChildMaxAge"), _is_individual, "YEARS"),
        ("studentsOnlyAboveAge", "Só estudantes acima de", ("household", "studentsOnlyAboveAge"), _is_individual, "YEARS"),
        ("clinicalQuestionnaire", "Questionário clínico obrigatório", ("clinicalQuestionnaire", "required"), None, None),
        ("medicalExamAboveAge", "Exame médico acima da idade", ("clinicalQuestionnaire", "medicalExamAboveAge"), None, "YEARS"),
        ("medicalExamAboveCapital", "Exame médico acima do capital", ("clinicalQuestionnaire", "medicalExamAboveCapital"), None, "MONEY"),
        ("groupMinInsured", "Dimensão mínima do grupo", ("group", "minInsured"), _is_group, "PEOPLE"),
        ("groupAdhesion", "Adesão", ("group", "adhesion"), _is_group, None),
        ("questionnaireWaivedAboveInsured", "Dispensa de questionário a partir de", ("group", "questionnaireWaivedAboveInsured"), _is_group, "PEOPLE"),
        ("premiumBasis", "Base do prémio", ("group", "premiumBasis"), _is_group, None),
        ("premiumPayer", "Quem paga o prémio", ("group", "premiumPayer"), _is_group, None),
        ("includesRetirees", "Inclui reformados", ("group", "includesRetirees"), _is_group, None),
        ("familyExtension", "Extensão à família", ("group", "familyExtension"), _is_group, None),
        ("continuityAfterLeaving", "Continuidade após saída", ("group", "continuityAfterLeaving"), _is_group, None),
    ])
    return _section("eligibility", "Elegibilidade", rows)


def _participation(items: list[dict[str, Any]]) -> dict[str, Any]:
    def selected(settings):
        if settings.get("costSharingModel") == "INTEGRAL":
            return _state(NOT_APPLICABLE)
        return _or_not_informed(settings.get("participationOption"))

    def options(settings):
        if settings.get("costSharingModel") == "INTEGRAL":
            return _state(NOT_APPLICABLE)
        return _or_not_informed(settings.get("participationOptions"))

    rows = [
        _row("participationOption", "Opção de participação escolhida", [selected(i["settings"]) for i in items]),
        _row("participationOptions", "Opções de participação disponíveis (A–E)", [options(i["settings"]) for i in items]),
    ]
    return _section("participation", "Condições financeiras", rows)


def _pre_existing_cell(settings: dict[str, Any]) -> dict[str, Any]:
    treatment = settings.get("preExistingTreatment")
    if not treatment:
        return _state(NOT_INFORMED)
    cell = _value(treatment)
    if treatment.get("mode") in _ASSESSED_PRE_EXISTING:
        cell["state"] = SUBJECT_TO_ASSESSMENT
    return cell


def _waiting_and_rules(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        _row("preExistingTreatment", "Doenças preexistentes", [_pre_existing_cell(i["settings"]) for i in items]),
        *_plan_rows(items, [
            ("accidentWaived", "Acidente dispensa carências", ("waitingRules", "accidentWaived"), None, None),
            ("groupMandatoryEliminatesWaiting", "Adesão obrigatória elimina carências", ("waitingRules", "groupMandatoryEliminatesWaiting"), _is_group, None),
            ("priorAuthInternments", "Autorização prévia — internamentos", ("priorAuthorization", "internments"), None, None),
            ("priorAuthHighCostExams", "Autorização prévia — exames de custo elevado", ("priorAuthorization", "highCostExams"), None, None),
            ("priorAuthScheduledSurgeries", "Autorização prévia — cirurgias programadas", ("priorAuthorization", "scheduledSurgeries"), None, None),
        ]),
    ]
    return _section("waitingAndRules", "Carências, preexistentes e autorizações", rows)


def _network(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _plan_rows(items, [
        ("networkRegions", "Rede convencionada — regiões", ("network", "regions"), _uses_network, None),
        ("medicalInflationPct", "Indexação de capitais (inflação médica)", ("capitalIndexation", "medicalInflationPct"), None, "PERCENT"),
        ("reviewOnRenewal", "Revisão dos capitais na renovação", ("capitalIndexation", "reviewOnRenewal"), None, None),
    ])
    return _section("network", "Rede e renovação", rows)


# --------------------------------------------------------------- coverages
def _limits_of(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [lim for lim in config.get("limits") or [] if isinstance(lim, dict)]


def _primary_capital(config: dict[str, Any]) -> dict[str, Any] | None:
    for lim in _limits_of(config):
        if lim.get("kind") in _PRIMARY_KINDS:
            return {"kind": lim["kind"], "kindLabel": GUARANTEE_FORMS[lim["kind"]], "amount": lim.get("amount")}
    events = [lim for lim in _limits_of(config) if lim.get("kind") == "PER_EVENT"]
    if events:  # várias quantias por evento (p.ex. parto normal / cesariana)
        return {"kind": "PER_EVENT", "kindLabel": GUARANTEE_FORMS["PER_EVENT"], "amount": events[0].get("amount"),
                "label": events[0].get("label")}
    return None


def _participation_cell(config: dict[str, Any], settings: dict[str, Any], block: str) -> dict[str, Any]:
    allowed = _ACCESS_BLOCKS.get(settings.get("accessSystem") or "", ("NETWORK", "REIMBURSEMENT"))
    if block not in allowed:
        return _state(NOT_APPLICABLE)
    if settings.get("costSharingModel") == "INTEGRAL":
        return _value({"type": "NONE"})
    spec = (config.get("participation") or {}).get(block)
    return _or_not_informed(spec)


def _coverage_cells(items: list[dict[str, Any]], code: str, build) -> list[dict[str, Any]]:
    cells = []
    for item in items:
        pb = item["coverages"].get(code)
        if pb is None:
            cells.append(_state(NOT_INCLUDED))
            continue
        config = pb.configuration_json or {}
        currency = config.get("currency") or item["settings"].get("currency") or "AOA"
        cells.append(build(config, item["settings"], currency))
    return cells


def _coverage_section(items: list[dict[str, Any]], code: str, benefit) -> dict[str, Any]:
    def inclusion(config, settings, currency):
        return _value(config.get("inclusion", "INCLUDED"))

    def capital(config, settings, currency):
        primary = _primary_capital(config)
        if primary is None:
            return _state(NOT_APPLICABLE if code == "ASSISTANCE_24H" else NOT_INFORMED)
        return _value(primary, currency=currency)

    def sublimits(config, settings, currency):
        primary = _primary_capital(config)
        subs = [
            lim for lim in _limits_of(config)
            if lim.get("kind") in _SUB_KINDS
            and not (primary and primary["kind"] == "PER_EVENT" and lim.get("kind") == "PER_EVENT"
                     and lim.get("label") == primary.get("label"))
        ]
        return _value(subs, currency=currency) if subs else _state(NOT_INFORMED)

    def quantity(config, settings, currency):
        qty = [lim for lim in _limits_of(config) if lim.get("kind") == "QUANTITY"]
        return _value(qty) if qty else _state(NOT_INFORMED)

    def coinsurance(config, settings, currency):
        pct = next((lim.get("pct") for lim in _limits_of(config) if lim.get("kind") == "COINSURANCE_PCT"), None)
        return _or_not_informed(pct)

    def participation(block):
        return lambda config, settings, currency: _participation_cell(config, settings, block)

    def waiting(key):
        def build(config, settings, currency):
            if key == "individual" and not _is_individual(settings) or key == "group" and not _is_group(settings):
                return _state(NOT_APPLICABLE)
            return _or_not_informed(_get(config, "waitingDays", key))
        return build

    def accident_waived(config, settings, currency):
        value = _get(config, "waitingDays", "accidentWaived")
        if value is None:
            value = _get(settings, "waitingRules", "accidentWaived")
        return _or_not_informed(value)

    def field(name, *, only_code: str | None = None):
        def build(config, settings, currency):
            value = config.get(name)
            if value is None and only_code is not None and code != only_code:
                return _state(NOT_APPLICABLE)
            return _or_not_informed(value)
        return build

    def prior_approval(config, settings, currency):
        return _value(bool(config.get("requiresPriorApproval", False)))

    def exclusions(config, settings, currency):
        items_ = [*(config.get("exclusions") or []), *(config.get("excludedItems") or [])]
        return _value(items_) if items_ else _state(NOT_INFORMED)

    spec = [
        ("inclusion", "Inclusão", inclusion, None),
        ("capital", "Capital principal", capital, "MONEY"),
        ("sublimits", "Sublimites e limites por ato/evento", sublimits, "MONEY"),
        ("quantityLimits", "Limites de quantidade", quantity, "COUNT"),
        ("coinsurancePct", "Comparticipação da seguradora", coinsurance, "PERCENT"),
        ("participationNetwork", "Participação — rede convencionada", participation("NETWORK"), None),
        ("participationReimbursement", "Participação — reembolso", participation("REIMBURSEMENT"), None),
        ("waitingIndividual", "Carência (individual)", waiting("individual"), "DAYS"),
        ("waitingGroup", "Carência (grupo)", waiting("group"), "DAYS"),
        ("waitingScheduledSurgery", "Carência — cirurgias programadas", waiting("scheduledSurgery"), "DAYS"),
        ("accidentWaived", "Acidente dispensa carência", accident_waived, None),
        ("requiresPriorApproval", "Aprovação prévia", prior_approval, None),
        ("maxDaysPerYear", "Máximo de dias por ano", field("maxDaysPerYear", only_code="HOSPITAL_DAILY_ALLOWANCE"), "DAYS"),
        ("timeDeductibleDays", "Franquia temporal", field("timeDeductibleDays", only_code="HOSPITAL_DAILY_ALLOWANCE"), "DAYS"),
        ("destinations", "Destinos", field("destinations", only_code="MEDICAL_EVACUATION"), None),
        ("closedDiseaseList", "Lista fechada de doenças", field("closedDiseaseList", only_code="CRITICAL_ILLNESS"), None),
        ("exclusions", "Exclusões da cobertura", exclusions, None),
    ]
    rows = [_row(key, label, _coverage_cells(items, code, build), unit) for key, label, build, unit in spec]
    # Uma cobertura ausente em todos os planos nunca chega aqui; atributos que
    # nenhum plano informa só fazem ruído: ficam de fora.
    rows = [r for r in rows if r["key"] == "inclusion" or any(c["state"] == VALUE or c["state"] == SUBJECT_TO_ASSESSMENT for c in r["cells"])]
    return _section(
        f"coverage.{code}", benefit.name, rows, kind="COVERAGE",
        coverageCode=code, coverageCategory=benefit.benefit_type,
    )


def _coverage_index(items: list[dict[str, Any]]) -> list[tuple[str, Any]]:
    benefits: dict[str, Any] = {}
    for item in items:
        for code, pb in item["coverages"].items():
            benefits.setdefault(code, pb.benefit)
    return sorted(benefits.items(), key=lambda kv: (kv[1].benefit_type != "BASE", kv[1].name or kv[0]))


def _capitals(items: list[dict[str, Any]], index: list[tuple[str, Any]]) -> dict[str, Any]:
    rows = []
    for code, benefit in index:
        def build(config, settings, currency):
            if config.get("inclusion") == "OPTIONAL":
                primary = _primary_capital(config)
                cell = _value(primary, currency=currency) if primary else _state(NOT_INFORMED)
                cell["optional"] = True
                return cell
            primary = _primary_capital(config)
            if primary is None:
                return _state(NOT_APPLICABLE if code == "ASSISTANCE_24H" else NOT_INFORMED)
            return _value(primary, currency=currency)
        rows.append(_row(code, benefit.name, _coverage_cells(items, code, build), "MONEY"))
    return _section(
        "capitals", "Capitais por cobertura", rows,
        note="Cada capital é o limite próprio da cobertura; os capitais não se somam entre coberturas.",
    )


# ----------------------------------------------------------------- premium
_PROPOSER_TYPE = {"INDIVIDUAL_FAMILY": "INDIVIDUAL", "GROUP": "ORGANISATION"}


def _parse_composition(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidPlanComparisonError("composition tem de ser um objeto")
    members = raw.get("members")
    if not isinstance(members, list) or not members:
        raise InvalidPlanComparisonError("composition.members: indique pelo menos uma pessoa")
    parsed = []
    for idx, member in enumerate(members):
        if not isinstance(member, dict):
            raise InvalidPlanComparisonError(f"composition.members[{idx}] tem de ser um objeto")
        age = member.get("age")
        if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 120:
            raise InvalidPlanComparisonError(f"composition.members[{idx}].age: idade entre 0 e 120")
        sex = member.get("sex") or "M"
        if sex not in ("M", "F"):
            raise InvalidPlanComparisonError(f"composition.members[{idx}].sex: M ou F")
        relationship = member.get("relationship")
        if relationship is not None and (not isinstance(relationship, str) or len(relationship) > 40):
            raise InvalidPlanComparisonError(f"composition.members[{idx}].relationship inválido")
        parsed.append({"age": age, "sex": sex, "relationship": relationship})
    selections = raw.get("selections") or {}
    if not isinstance(selections, dict):
        raise InvalidPlanComparisonError("composition.selections tem de ser um objeto indexado por planId")
    return {"members": parsed, "paymentFrequency": raw.get("paymentFrequency"), "selections": selections}


def _price(items: list[dict[str, Any]], composition: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.business_config.application import tariff_service

    frequency = composition["paymentFrequency"]
    if frequency is not None and frequency not in tariff_service.FREQUENCIES:
        raise InvalidPlanComparisonError(f"composition.paymentFrequency: use {list(tariff_service.FREQUENCIES)}")
    results = []
    for item in items:
        plan = item["plan"]
        segment = item["settings"].get("segment")
        result: dict[str, Any] = {"planId": str(plan.id)}
        try:
            simulated = tariff_service.simulate_tariff(
                plan.product,
                plan_id=plan.id,
                members=[dict(m) for m in composition["members"]],
                proposer_type=_PROPOSER_TYPE.get(segment, "INDIVIDUAL"),
                selection=composition["selections"].get(str(plan.id)),
                payment_frequency=frequency,
            )
        except DomainProblem as exc:
            result.update({"available": False, "reason": str(exc)})
        else:
            result.update({
                "available": True,
                "currencyCode": simulated.get("currencyCode"),
                "totalAmount": simulated.get("totalAmount"),
                "installments": simulated.get("installments") or {},
                "referenceDate": simulated.get("referenceDate"),
            })
        results.append(result)
    return results


def _premium_section(results: list[dict[str, Any]], frequency: str | None) -> dict[str, Any]:
    from apps.business_config.application.tariff_service import FREQUENCIES

    def cell(result: dict[str, Any], amount: Any) -> dict[str, Any]:
        if not result["available"]:
            return {"state": NOT_INFORMED, "value": None, "reason": result["reason"]}
        return _or_not_informed(amount, currency=result.get("currencyCode"))

    rows = [_row("totalAmount", "Prémio total anual da composição", [cell(r, r.get("totalAmount")) for r in results], "MONEY")]
    labels = {"ANUAL": "Prestação anual", "SEMESTRAL": "Prestação semestral", "TRIMESTRAL": "Prestação trimestral",
              "MENSAL": "Prestação mensal"}
    for code in ([frequency] if frequency else list(FREQUENCIES)):
        rows.append(_row(
            f"installment.{code}", labels.get(code, code),
            [cell(r, (r.get("installments") or {}).get(code)) for r in results], "MONEY",
        ))
    return _section("premium", "Prémio para a composição indicada", rows)


def _premium_facts(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priced = [(r["planId"], _decimal(r.get("totalAmount")), r.get("currencyCode")) for r in results if r["available"]]
    priced = [p for p in priced if p[1] is not None]
    facts: list[dict[str, Any]] = []
    unavailable = [r["planId"] for r in results if not r["available"]]
    if unavailable:
        facts.append({"type": "PREMIUM_UNAVAILABLE", "planIds": unavailable,
                      "message": "Não foi possível calcular o prémio de alguns planos para esta composição."})
    if len(priced) < 2:
        return facts
    if len({p[2] for p in priced}) > 1:
        facts.append({"type": "PREMIUM_NOT_COMPARABLE", "planIds": [p[0] for p in priced],
                      "message": "Os prémios estão em moedas diferentes e não são comparáveis diretamente."})
        return facts
    lowest = min(p[1] for p in priced)
    facts.append({
        "type": "PREMIUM_LOWEST", "planIds": [p[0] for p in priced if p[1] == lowest],
        "amount": str(lowest), "currency": priced[0][2], "message": "Prémio mais baixo para esta composição.",
    })
    for plan_id, amount, currency in priced:
        if amount != lowest:
            facts.append({
                "type": "PREMIUM_DIFFERENCE", "planIds": [plan_id], "amount": str(amount),
                "difference": str(amount - lowest), "currency": currency,
                "message": "Diferença de prémio face ao plano mais barato.",
            })
    return facts


# ----------------------------------------------------------------- summary
def _summary(items: list[dict[str, Any]], index: list[tuple[str, Any]], headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Diferenças factuais, sem eleger um plano «melhor». As quantias seguem
    em bruto (formatadas no frontend); `message` nunca leva valores."""
    facts: list[dict[str, Any]] = []
    plan_ids = [h["planId"] for h in headers]

    for code, benefit in index:
        present = [pid for pid, item in zip(plan_ids, items) if code in item["coverages"]]
        if len(present) != len(items):
            facts.append({
                "type": "COVERAGE_NOT_IN_ALL",
                "coverageCode": code,
                "planIds": present,
                "message": f"«{benefit.name}» só está disponível em {len(present)} dos {len(items)} planos.",
            })
            continue
        inclusions = {pid: item["coverages"][code].configuration_json.get("inclusion", "INCLUDED")
                      for pid, item in zip(plan_ids, items)}
        if len(set(inclusions.values())) > 1:
            facts.append({
                "type": "COVERAGE_OPTIONAL_IN_SOME",
                "coverageCode": code,
                "planIds": [pid for pid, inc in inclusions.items() if inc == "OPTIONAL"],
                "message": f"«{benefit.name}» é incluída nuns planos e opcional noutros.",
            })

        capitals = []
        for pid, item in zip(plan_ids, items):
            config = item["coverages"][code].configuration_json or {}
            primary = _primary_capital(config)
            amount = _decimal(primary["amount"]) if primary else None
            currency = config.get("currency") or item["settings"].get("currency") or "AOA"
            capitals.append((pid, primary["kind"] if primary else None, amount, currency))
        if any(c[2] is None for c in capitals):
            continue
        if len({c[1] for c in capitals}) > 1 or len({c[3] for c in capitals}) > 1:
            facts.append({
                "type": "CAPITAL_NOT_COMPARABLE",
                "coverageCode": code,
                "planIds": plan_ids,
                "message": f"«{benefit.name}»: os capitais têm forma de garantia ou moeda diferentes e não são comparáveis diretamente.",
            })
            continue
        highest = max(capitals, key=lambda c: c[2])
        lowest = min(capitals, key=lambda c: c[2])
        if highest[2] != lowest[2]:
            facts.append({
                "type": "CAPITAL_HIGHER",
                "coverageCode": code,
                "planIds": [c[0] for c in capitals if c[2] == highest[2]],
                "amount": str(highest[2]),
                "difference": str(highest[2] - lowest[2]),
                "currency": highest[3],
                "message": f"«{benefit.name}»: capital mais alto.",
            })

    for key, label in (("accessSystem", "sistema de acesso"), ("costSharingModel", "modelo de participação")):
        values = {item["settings"].get(key) for item in items}
        if len(values) > 1:
            facts.append({"type": "PLAN_SETTING_DIFFERS", "setting": key, "planIds": plan_ids,
                          "message": f"Os planos têm {label} diferente."})
    return facts


def _warnings(items: list[dict[str, Any]], headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    segments = {h["segment"] for h in headers}
    if len(segments) > 1:
        warnings.append({
            "code": "SEGMENT_MISMATCH",
            "message": "Está a comparar planos individuais/familiares com planos de grupo: as condições de contratação são diferentes.",
        })
    currencies = {h["currency"] for h in headers}
    if len(currencies) > 1:
        warnings.append({
            "code": "CURRENCY_MISMATCH",
            "message": "Os planos usam moedas diferentes: os valores não são comparáveis sem conversão.",
        })
    for header, item in zip(headers, items):
        plan_id = header["planId"]
        if header["planStatus"] != PlanStatus.ACTIVE.value:
            warnings.append({"code": "PLAN_INACTIVE", "planId": plan_id, "message": f"O plano {header['planCode']} está inativo."})
        if header["productStatus"] != ProductStatus.ACTIVE.value:
            warnings.append({
                "code": "PRODUCT_NOT_ACTIVE", "planId": plan_id,
                "message": f"O produto {header['productCode']} não está ativo: as condições podem ainda mudar.",
            })
        if not validate_plan(plan=item["plan"])["valid"]:
            warnings.append({
                "code": "PLAN_CONFIGURATION_INVALID", "planId": plan_id,
                "message": f"O plano {header['planCode']} tem erros de configuração: alguns valores podem estar incompletos.",
            })
    return warnings


# -------------------------------------------------------------------- API
def compare_plans(
    *, plan_ids: list[str], only_differences: bool = False, composition: dict[str, Any] | None = None
) -> dict[str, Any]:
    ids = _parse_ids(plan_ids)
    parsed_composition = _parse_composition(composition)
    items = _load(ids)
    headers = [_header(item) for item in items]
    index = _coverage_index(items)

    premium_results = _price(items, parsed_composition) if parsed_composition else None

    sections = [
        _identification(items),
        *([_premium_section(premium_results, parsed_composition["paymentFrequency"])] if premium_results else []),
        _capitals(items, index),
        *[_coverage_section(items, code, benefit) for code, benefit in index],
        _participation(items),
        _eligibility(items),
        _waiting_and_rules(items),
        _network(items),
    ]
    if only_differences:
        filtered = []
        for section in sections:
            rows = [r for r in section["rows"] if r["different"]]
            if rows:
                filtered.append({**section, "rows": rows})
        sections = filtered

    return {
        "plans": headers,
        "onlyDifferences": only_differences,
        "sections": sections,
        "summary": [*(_premium_facts(premium_results) if premium_results else []), *_summary(items, index, headers)],
        "warnings": _warnings(items, headers),
        "pricing": _pricing_block(premium_results, parsed_composition),
    }


def _pricing_block(results: list[dict[str, Any]] | None, composition: dict[str, Any] | None) -> dict[str, Any]:
    if results is None or composition is None:
        return {
            "available": False,
            "message": "O prémio depende da composição e das idades: envie composition (POST) para o comparar.",
            "results": [],
        }
    return {
        "available": any(r["available"] for r in results),
        "message": "Cálculo real de uma cotação de exemplo por plano; nada foi gravado.",
        "persisted": False,
        "members": composition["members"],
        "paymentFrequency": composition["paymentFrequency"],
        "results": results,
    }
