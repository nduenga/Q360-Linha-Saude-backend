"""Cenários de cotação (R5): criar, clonar, alterar, comparar lado a lado,
selecionar (o que gera a proposta) e aplicar à cotação.

Um cenário é um conjunto de **parâmetros** — coberturas opcionais escolhidas,
opção de participação A–E, alterações de capitais/participação "e se..." e
ajustes (agravamentos/descontos) — sobre a mesma população e plano da
cotação. O resultado vem do **mesmo motor** (`preview_pricing`): nada é
gravado no motor, nenhuma cotação oficial é alterada ("Não altera quote
oficial", Q360-S5-02). O resultado fica guardado no cenário com um
`inputs_hash`; se o plano, as tarifas ou a população mudarem, o cenário
aparece como `stale` até ser recalculado.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any, Callable

from django.db import IntegrityError, transaction

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.application.plan_dimensions import resolve_plan_pricing_context
from apps.pricing.application.pricing_engine import preview_pricing
from apps.pricing.application.rating_table_service import resolve_rating_table
from apps.pricing.domain.money import round_amount
from apps.pricing.infrastructure.parameter_repository import resolve_pricing_parameter_set
from apps.product.infrastructure.models import PlanBenefit
from apps.quote.application import quote_service, simulator_service
from apps.quote.domain.enums import QuoteStatus
from apps.quote.domain.errors import QuoteStateError, ReferencedEntityNotFoundError, RowVersionMismatchError
from apps.quote.infrastructure.models import Quote, QuoteAdjustment, QuoteScenario

_audit = AuditService(DjangoAuditRepositoryAdapter())
_EDITABLE = (QuoteStatus.DRAFT.value, QuoteStatus.READY.value)


class ScenarioNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


class DuplicateScenarioNameError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


class ScenarioStateError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


def _require_editable(quote: Quote) -> None:
    if quote.status not in _EDITABLE:
        raise QuoteStateError(f"Quote {quote.id} is {quote.status}; scenarios can only be changed while DRAFT or READY")


def _fmt(value: Decimal) -> str:
    return format(Decimal(str(value)).normalize(), "f")


# ------------------------------------------------------------- parameters
def default_parameters(quote: Quote) -> dict[str, Any]:
    """The quote's current state as scenario parameters (the starting point
    of every new scenario)."""
    return {
        "selection": quote.selection_json or {},
        "adjustments": [
            {k: v for k, v in item.items() if k != "id"} for item in quote_service.active_adjustments_for_context(quote)
        ],
    }


def normalise_parameters(quote: Quote, raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or set(raw) - {"selection", "adjustments", "projection"}:
        raise ReferencedEntityNotFoundError(
            "parameters must be an object with 'selection', 'adjustments' and/or 'projection'"
        )
    plan_context = resolve_plan_pricing_context(plan=quote.plan, selection=raw.get("selection") or {})
    adjustments = raw.get("adjustments") or []
    if not isinstance(adjustments, list):
        raise ReferencedEntityNotFoundError("parameters.adjustments must be a list")
    clean: list[dict[str, Any]] = []
    for spec in adjustments:
        if not isinstance(spec, dict):
            raise ReferencedEntityNotFoundError("each adjustment must be an object")
        valid = simulator_service._validate_adjustment_spec(quote, spec)
        item: dict[str, Any] = {"kind": valid["kind"], "value": _fmt(valid["value"]), "scope": valid["scope"], "memberId": valid["memberId"]}
        if spec.get("reason"):
            item["reason"] = spec["reason"]
        clean.append(item)
    result: dict[str, Any] = {"selection": plan_context.selection, "adjustments": clean}
    projection = raw.get("projection")
    if projection is not None:
        result["projection"] = _validate_projection_link(quote, projection)
    return result


def _validate_projection_link(quote: Quote, projection: Any) -> dict[str, str]:
    """Links a claims projection (R2) to the scenario: `{"projectionRunId", "scenario"}`
    — the run must exist and belong to the quote's client."""
    from apps.claims.application import projection_service

    if not isinstance(projection, dict) or set(projection) - {"projectionRunId", "scenario"}:
        raise ReferencedEntityNotFoundError("parameters.projection must be {projectionRunId, scenario}")
    scenario_name = projection.get("scenario")
    if scenario_name not in projection_service.SCENARIOS:
        raise ReferencedEntityNotFoundError(f"projection.scenario must be one of {list(projection_service.SCENARIOS)}")
    try:
        run = projection_service.get_run(projection.get("projectionRunId"))
    except DomainProblem as exc:
        raise ReferencedEntityNotFoundError(str(exc)) from exc
    if run.proposer_id != quote.proposer_id:
        raise ReferencedEntityNotFoundError("The projection belongs to a different client")
    chosen = run.result_json["scenarios"][scenario_name]
    return {
        "projectionRunId": str(run.id),
        "scenario": scenario_name,
        "expectedLossRatioPct": chosen["expectedLossRatioPct"],
        "premiumImpactPct": chosen["premiumImpactPct"],
    }


def _context_for(quote: Quote, parameters: dict[str, Any]) -> tuple[dict, list[uuid.UUID]]:
    adjustments = [{"id": f"scn-{i}", **spec} for i, spec in enumerate(parameters.get("adjustments", []))]
    return quote_service.build_pricing_context(quote, selection=parameters.get("selection") or {}, adjustments=adjustments)


def _inputs_hash(quote: Quote, context: dict, member_ids: list[uuid.UUID]) -> str:
    rating = resolve_rating_table(code=context["ratingTableCode"], effective_date=quote.effective_date)
    params = resolve_pricing_parameter_set(code=context["parameterSetCode"], effective_date=quote.effective_date)
    plan_configs = {
        pb.benefit.code: pb.configuration_json
        for pb in PlanBenefit.objects.filter(plan=quote.plan).select_related("benefit")
    }
    payload = {
        "context": context,
        "members": sorted(str(m) for m in member_ids),
        "plan": {"settings": quote.plan.settings_json, "coverages": plan_configs},
        "effectiveDate": quote.effective_date.isoformat(),
        "ratingTable": [str(rating.id), rating.version_no] if rating else None,
        "parameterSet": [str(params.id), params.version_no] if params else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _calculate(quote: Quote, parameters: dict[str, Any], render: Callable) -> tuple[dict[str, Any], str]:
    context, member_ids = _context_for(quote, parameters)
    rendered = preview_pricing(
        plan_id=quote.plan_id,
        effective_date=quote.effective_date,
        member_ids=member_ids,
        context=context,
        correlation_id=None,
        render=render,
    )
    result = {
        "totalAmount": rendered["totalAmount"],
        "currencyCode": rendered["currencyCode"],
        "calculatedAt": rendered.get("calculatedAt"),
        "warnings": rendered.get("warnings", []),
        "components": rendered["components"],
        "versions": rendered.get("versions", {}),
        "memberCount": len(member_ids),
    }
    return json.loads(json.dumps(result, default=str)), _inputs_hash(quote, context, member_ids)


# ------------------------------------------------------------------- CRUD
def get_scenario(scenario_id: uuid.UUID) -> QuoteScenario:
    scenario = QuoteScenario.objects.select_related("quote", "quote__plan").filter(id=scenario_id).first()
    if scenario is None:
        raise ScenarioNotFoundError(f"Scenario {scenario_id} does not exist")
    return scenario


def is_stale(scenario: QuoteScenario) -> bool:
    quote = scenario.quote
    context, member_ids = _context_for(quote, scenario.parameters_json)
    return scenario.inputs_hash != _inputs_hash(quote, context, member_ids)


def list_scenarios(*, quote: Quote):
    return QuoteScenario.objects.filter(quote=quote).order_by("created_at", "name")


def _unique_name(quote: Quote, wanted: str) -> str:
    existing = set(QuoteScenario.objects.filter(quote=quote).values_list("name", flat=True))
    if wanted not in existing:
        return wanted
    counter = 2
    while f"{wanted} {counter}" in existing:
        counter += 1
    return f"{wanted} {counter}"


def create_scenario(
    *,
    quote: Quote,
    name: str,
    description: str | None,
    parameters: dict[str, Any] | None,
    render: Callable,
    base: QuoteScenario | None = None,
) -> QuoteScenario:
    _require_editable(quote)
    clean = normalise_parameters(quote, parameters if parameters is not None else default_parameters(quote))
    result, inputs_hash = _calculate(quote, clean, render)
    actor = CurrentActorProvider.get()
    try:
        with transaction.atomic():
            scenario = QuoteScenario.objects.create(
                tenant_id=quote.tenant_id,
                quote=quote,
                name=name,
                description=description,
                parameters_json=clean,
                result_json=result,
                inputs_hash=inputs_hash,
                base_scenario=base,
                created_by=actor.actor_id if actor else "unknown",
            )
    except IntegrityError as exc:
        raise DuplicateScenarioNameError(f"Quote {quote.id} already has a scenario named '{name}'") from exc
    _audit.record(
        action="quote.scenario_created",
        entity_type="QuoteScenario",
        entity_id=str(scenario.id),
        metadata=change_metadata(
            after={"name": name, "parameters": clean, "totalAmount": result["totalAmount"]},
            quoteId=str(quote.id),
            baseScenarioId=str(base.id) if base else None,
        ),
    )
    return scenario


def update_scenario(
    *,
    scenario: QuoteScenario,
    name: str,
    description: str | None,
    parameters: dict[str, Any] | None,
    row_version: int,
    render: Callable,
) -> QuoteScenario:
    quote = scenario.quote
    _require_editable(quote)
    before = {"name": scenario.name, "parameters": scenario.parameters_json, "totalAmount": scenario.result_json.get("totalAmount")}
    clean = normalise_parameters(quote, parameters) if parameters is not None else scenario.parameters_json
    result, inputs_hash = _calculate(quote, clean, render)
    try:
        with transaction.atomic():
            updated = QuoteScenario.objects.filter(id=scenario.id, row_version=row_version).update(
                name=name,
                description=description,
                parameters_json=clean,
                result_json=result,
                inputs_hash=inputs_hash,
                row_version=row_version + 1,
            )
            if updated == 0:
                raise RowVersionMismatchError(
                    f"Scenario {scenario.id} rowVersion {row_version} does not match the current version"
                )
    except IntegrityError as exc:
        raise DuplicateScenarioNameError(f"Quote {quote.id} already has a scenario named '{name}'") from exc
    scenario = get_scenario(scenario.id)
    _audit.record(
        action="quote.scenario_updated",
        entity_type="QuoteScenario",
        entity_id=str(scenario.id),
        metadata=change_metadata(
            before=before,
            after={"name": name, "parameters": clean, "totalAmount": result["totalAmount"]},
            impact={"previousTotal": before["totalAmount"], "newTotal": result["totalAmount"]},
        ),
    )
    return scenario


def recalculate_scenario(*, scenario: QuoteScenario, render: Callable) -> QuoteScenario:
    quote = scenario.quote
    _require_editable(quote)
    previous = scenario.result_json.get("totalAmount")
    result, inputs_hash = _calculate(quote, scenario.parameters_json, render)
    QuoteScenario.objects.filter(id=scenario.id).update(
        result_json=result, inputs_hash=inputs_hash, row_version=scenario.row_version + 1
    )
    scenario = get_scenario(scenario.id)
    _audit.record(
        action="quote.scenario_recalculated",
        entity_type="QuoteScenario",
        entity_id=str(scenario.id),
        metadata=change_metadata(impact={"previousTotal": previous, "newTotal": result["totalAmount"]}),
    )
    return scenario


def clone_scenario(*, scenario: QuoteScenario, name: str | None, render: Callable) -> QuoteScenario:
    quote = scenario.quote
    wanted = name or f"{scenario.name} (cópia)"
    return create_scenario(
        quote=quote,
        name=_unique_name(quote, wanted) if name is None else wanted,
        description=scenario.description,
        parameters=json.loads(json.dumps(scenario.parameters_json)),
        render=render,
        base=scenario,
    )


def delete_scenario(*, scenario: QuoteScenario) -> None:
    _require_editable(scenario.quote)
    if scenario.is_selected:
        raise ScenarioStateError("The selected scenario cannot be deleted: select another one first")
    QuoteScenario.objects.filter(id=scenario.id).delete()
    _audit.record(
        action="quote.scenario_deleted",
        entity_type="QuoteScenario",
        entity_id=str(scenario.id),
        metadata=change_metadata(before={"name": scenario.name, "parameters": scenario.parameters_json}),
    )


def select_scenario(*, scenario: QuoteScenario) -> QuoteScenario:
    """The scenario a proposal is generated from. Exactly one per quote."""
    _require_editable(scenario.quote)
    with transaction.atomic():
        QuoteScenario.objects.filter(quote=scenario.quote, is_selected=True).exclude(id=scenario.id).update(is_selected=False)
        QuoteScenario.objects.filter(id=scenario.id).update(is_selected=True)
    _audit.record(
        action="quote.scenario_selected",
        entity_type="QuoteScenario",
        entity_id=str(scenario.id),
        metadata=change_metadata(after={"name": scenario.name}, quoteId=str(scenario.quote_id)),
    )
    return get_scenario(scenario.id)


def apply_scenario(*, scenario: QuoteScenario, reason: str | None) -> Quote:
    """Makes the scenario the quote's official state: its selection becomes
    the quote's, the quote's ACTIVE adjustments are replaced by the
    scenario's (the old ones stay as REMOVED, nothing is deleted) and the
    quote is re-priced. Authority limits apply to every adjustment."""
    quote = scenario.quote
    _require_editable(quote)
    reason = require_reason(reason)
    actor = CurrentActorProvider.get()
    specs = scenario.parameters_json.get("adjustments", [])
    with transaction.atomic():
        for spec in specs:
            clean = simulator_service._validate_adjustment_spec(quote, spec)
            simulator_service._enforce_authority(quote, clean)
        baseline_context, member_ids = quote_service.build_pricing_context(quote)
        previous = simulator_service._preview_total(quote, baseline_context, member_ids)["totalAmount"]

        from django.utils import timezone

        QuoteAdjustment.objects.filter(quote=quote, status="ACTIVE").update(
            status="REMOVED",
            removed_by=actor.actor_id if actor else "unknown",
            removed_at=timezone.now(),
            removed_reason=f"Substituído pelo cenário '{scenario.name}': {reason}",
        )
        for spec in specs:
            clean = simulator_service._validate_adjustment_spec(quote, spec)
            QuoteAdjustment.objects.create(
                tenant_id=quote.tenant_id,
                quote=quote,
                kind=clean["kind"],
                value=clean["value"],
                scope=clean["scope"],
                member_id=clean["memberId"],
                reason=spec.get("reason") or f"Cenário '{scenario.name}': {reason}",
                applied_by=actor.actor_id if actor else "unknown",
            )
        Quote.objects.filter(id=quote.id).update(
            selection_json=scenario.parameters_json.get("selection") or {}, row_version=quote.row_version + 1
        )
        quote.refresh_from_db()
        quote_service._demote_to_draft_if_ready(quote)
        quote.refresh_from_db()
        quote = simulator_service._reprice(quote)
        new_total = round_amount(quote.latest_pricing_run.total_amount) if quote.latest_pricing_run_id else None
    _audit.record(
        action="quote.scenario_applied",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(
            after={"scenarioId": str(scenario.id), "name": scenario.name, "parameters": scenario.parameters_json},
            reason=reason,
            impact=simulator_service._impact(previous, str(new_total) if new_total is not None else None, quote.currency_code),
        ),
    )
    return quote


# ---------------------------------------------------------------- compare
def _component_totals(components: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per component code, one comparable number: BASE/TOTAL = sum of the
    result; ADJUSTMENT = sum of the adjustment amount; FACTOR = the factor."""
    out: dict[str, dict[str, Any]] = {}
    for component in components:
        entry = out.setdefault(component["code"], {"type": component["type"], "amount": Decimal("0"), "factor": None})
        if component["type"] in ("BASE", "TOTAL"):
            entry["amount"] += Decimal(component["resultAmount"])
        elif component["type"] == "ADJUSTMENT":
            entry["amount"] += Decimal(component["adjustmentAmount"] or "0")
        elif component["type"] == "FACTOR":
            entry["factor"] = component["factorValue"]
    return out


def compare_scenarios(*, quote: Quote, scenario_ids: list[uuid.UUID] | None) -> dict[str, Any]:
    queryset = QuoteScenario.objects.filter(quote=quote).order_by("created_at", "name")
    if scenario_ids:
        queryset = queryset.filter(id__in=scenario_ids)
    scenarios = list(queryset)
    if scenario_ids and len(scenarios) != len(set(scenario_ids)):
        raise ScenarioNotFoundError("One or more scenarios do not belong to this quote")
    if len(scenarios) < 2:
        raise ReferencedEntityNotFoundError("At least two scenarios are needed to compare")

    contexts = {s.id: resolve_plan_pricing_context(plan=quote.plan, selection=s.parameters_json.get("selection") or {}) for s in scenarios}
    totals = {s.id: Decimal(s.result_json["totalAmount"]) for s in scenarios}
    first = scenarios[0]
    currency = first.result_json.get("currencyCode")

    header = []
    for s in scenarios:
        plan_context = contexts[s.id]
        header.append(
            {
                "id": str(s.id),
                "name": s.name,
                "isSelected": s.is_selected,
                "stale": is_stale(s),
                "totalAmount": s.result_json["totalAmount"],
                "deltaVsFirst": str(round_amount(totals[s.id] - totals[first.id])),
                "deltaPercentVsFirst": (
                    str(((totals[s.id] - totals[first.id]) / totals[first.id] * Decimal("100")).quantize(Decimal("0.01")))
                    if totals[first.id]
                    else None
                ),
                "participationOption": plan_context.participation_option.code if plan_context.participation_option else None,
                "optionalCoverages": list(plan_context.optional_coverage_codes),
                "adjustments": s.parameters_json.get("adjustments", []),
                "warnings": s.result_json.get("warnings", []),
                "projection": s.parameters_json.get("projection"),
            }
        )

    coverage_codes = sorted({c["code"] for ctx in contexts.values() for c in ctx.coverages})
    coverages = []
    for code in coverage_codes:
        values: dict[str, Any] = {}
        meta: dict[str, Any] = {}
        for s in scenarios:
            detail = next((c for c in contexts[s.id].coverages if c["code"] == code), None)
            meta = meta or ({"code": code, "name": detail["name"], "category": detail["category"]} if detail else {})
            if detail is None:
                continue
            cfg = detail["configuration"]
            values[str(s.id)] = {
                "contracted": detail["contracted"],
                "inclusion": detail["inclusion"],
                "limits": cfg.get("limits", []),
                "participation": cfg.get("participation", {}),
                "waitingDays": cfg.get("waitingDays", {}),
                "currency": cfg.get("currency", "AOA"),
            }
        distinct = {json.dumps(v, sort_keys=True) for v in values.values()}
        coverages.append({**meta, "values": values, "differs": len(distinct) > 1})

    component_codes: list[str] = []
    per_scenario_components: dict[uuid.UUID, dict[str, dict[str, Any]]] = {}
    for s in scenarios:
        per_scenario_components[s.id] = _component_totals(s.result_json.get("components", []))
        for code in per_scenario_components[s.id]:
            if code not in component_codes:
                component_codes.append(code)
    components = []
    for code in component_codes:
        values = {}
        for s in scenarios:
            entry = per_scenario_components[s.id].get(code)
            values[str(s.id)] = None if entry is None else {
                "amount": str(round_amount(entry["amount"])) if entry["type"] in ("BASE", "TOTAL", "ADJUSTMENT") else None,
                "factor": entry["factor"],
            }
        kind = next((per_scenario_components[s.id][code]["type"] for s in scenarios if code in per_scenario_components[s.id]), None)
        components.append(
            {"code": code, "type": kind, "values": values, "differs": len({json.dumps(v, sort_keys=True) for v in values.values()}) > 1}
        )

    lowest = min(scenarios, key=lambda s: totals[s.id])
    highest = max(scenarios, key=lambda s: totals[s.id])
    return {
        "quoteId": str(quote.id),
        "currencyCode": currency,
        "scenarios": header,
        "summary": {
            "lowest": {"id": str(lowest.id), "name": lowest.name, "totalAmount": str(round_amount(totals[lowest.id]))},
            "highest": {"id": str(highest.id), "name": highest.name, "totalAmount": str(round_amount(totals[highest.id]))},
            "spread": str(round_amount(totals[highest.id] - totals[lowest.id])),
        },
        "coverages": coverages,
        "components": components,
    }


def comparison_sheets(comparison: dict[str, Any]) -> dict[str, list[list[Any]]]:
    """Flat rows of the comparison, one sheet per section (XLSX/CSV export)."""
    scenarios = comparison["scenarios"]
    names = [s["name"] for s in scenarios]
    summary = [["Cenário", "Prémio total", "Δ vs 1.º", "Δ % vs 1.º", "Opção de participação", "Coberturas opcionais", "Selecionado", "Desatualizado"]]
    for s in scenarios:
        summary.append(
            [s["name"], s["totalAmount"], s["deltaVsFirst"], s["deltaPercentVsFirst"], s["participationOption"],
             ", ".join(s["optionalCoverages"]), "sim" if s["isSelected"] else "", "sim" if s["stale"] else ""]
        )
    coverage_rows: list[list[Any]] = [["Cobertura", "Categoria", "Difere", *names]]
    for cov in comparison["coverages"]:
        cells = []
        for s in scenarios:
            value = cov["values"].get(s["id"])
            if value is None:
                cells.append("—")
                continue
            capital = next((lim.get("amount") for lim in value["limits"] if lim.get("kind") in ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED", "BIENNIAL", "FIXED_AMOUNT")), None)
            cells.append(f"{'contratada' if value['contracted'] else 'não contratada'} ({value['inclusion']}) capital={capital or '—'} {value['currency']}")
        coverage_rows.append([cov.get("name") or cov["code"], cov.get("category"), "sim" if cov["differs"] else "", *cells])
    component_rows: list[list[Any]] = [["Componente", "Tipo", "Difere", *names]]
    for comp in comparison["components"]:
        cells = []
        for s in scenarios:
            value = comp["values"].get(s["id"])
            cells.append("—" if value is None else (value["amount"] if value["amount"] is not None else f"×{value['factor']}"))
        component_rows.append([comp["code"], comp["type"], "sim" if comp["differs"] else "", *cells])
    return {"Resumo": summary, "Coberturas": coverage_rows, "Componentes": component_rows}
