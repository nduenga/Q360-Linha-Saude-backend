"""Aplica a configuração de negócio publicada às definições dos motores.

  - `effective_plan_settings`  : definições do plano com idades, grupo, análise
    médica, renovação, rede, estrangeiro, aceitação e preexistências;
  - `apply_coverage_overlay`   : capitais, sublimites, participação, carências,
    inclusão/disponibilidade e evacuação de cada cobertura;
  - `effective_exclusions`     : exclusões habituais + as do negócio;
  - `plan_availability`        : planos que o negócio desativou.

Sem configuração publicada a função devolve exatamente o que recebeu. Uma
linha de negócio que viole as invariantes da cobertura é ignorada (com aviso
`BUSINESS_CONFIG_OVERLAY_REJECTED`), nunca grava lixo no cálculo.
"""
from __future__ import annotations

import copy
import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.application.readers import (
    BusinessSnapshot,
    integer,
    matches_coverage,
    matches_plan,
    number,
)
from apps.foundation.domain.problem import DomainProblem
from apps.product.domain.coverage_config import validate_coverage_config

_PRIMARY_KINDS = ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED", "BIENNIAL", "FIXED_AMOUNT")
_CURRENCY = {"KZ": "AOA", "AOA": "AOA", "USD": "USD"}


def _money(raw: Any) -> str | None:
    if raw in (None, ""):
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    return format(value, "f") if value > 0 else None


def _generic_first(rows: list[dict[str, Any]], key: str = "plan") -> list[dict[str, Any]]:
    """Linhas gerais primeiro, específicas depois: a mais específica prevalece."""
    return sorted(rows, key=lambda r: 1 if r.get(key) else 0)


def _as_bool(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    return None


# --------------------------------------------------------------------- plan
def plan_availability(plan, on: datetime.date | None = None, snapshot: BusinessSnapshot | None = None) -> tuple[bool, str | None]:
    snap = snapshot or BusinessSnapshot.load(on)
    for row in snap.rows("product.plans", "plans"):
        code = str(row.get("code") or "").strip().casefold()
        if code and code in {str(plan.code).casefold(), str(plan.name).casefold()} and row.get("active") is False:
            return False, f"O plano '{plan.code}' está desativado na configuração de negócio."
    return True, None


def effective_plan_settings(plan, on: datetime.date | None = None, snapshot: BusinessSnapshot | None = None) -> dict[str, Any]:
    settings = copy.deepcopy(plan.settings_json or {})
    snap = snapshot or BusinessSnapshot.load(on)
    if not snap.values:
        return settings

    for row in _generic_first(snap.rows("product.age_limits", "items")):
        if not matches_plan(row.get("plan"), plan, settings):
            continue
        entry_max, renewal_max = integer(row.get("entry_max_age")), integer(row.get("renewal_max_age"))
        if entry_max is not None:
            settings["entryAge"] = {**(settings.get("entryAge") or {"min": 0}), "max": entry_max}
        if renewal_max is not None:
            settings["permanenceAge"] = {**(settings.get("permanenceAge") or {}), "max": renewal_max}

    group = snap.get("group.rules") or {}
    if group and settings.get("segment") == "GROUP":
        merged = dict(settings.get("group") or {})
        minimum = integer(group.get("minimum_members"))
        if minimum is not None:
            merged["minInsured"] = minimum
        if group.get("below_minimum_behavior"):
            merged["belowMinimumBehavior"] = group["below_minimum_behavior"]
        mandatory = _as_bool(group.get("mandatory_enrolment"))
        if mandatory is not None:
            merged["adhesion"] = "MANDATORY" if mandatory else "VOLUNTARY"
        waived = integer(group.get("questionnaire_exemption_threshold"))
        if waived is not None:
            merged["questionnaireWaivedAboveInsured"] = waived
        threshold, share = number(group.get("experience_loss_ratio_threshold")), number(group.get("profit_share_percent"))
        if threshold is not None:
            merged["profitSharing"] = {
                **(merged.get("profitSharing") or {}),
                "lossRatioThresholdPct": threshold,
                **({"sharePct": share} if share is not None else {}),
            }
        settings["group"] = merged

    review = snap.get("underwriting.medical_review") or {}
    if review:
        questionnaire = dict(settings.get("clinicalQuestionnaire") or {})
        age = integer(review.get("automatic_acceptance_max_age"))
        capital = _money(review.get("capital_review_threshold"))
        if age is not None:
            questionnaire["medicalExamAboveAge"] = age
        if capital is not None:
            questionnaire["medicalExamAboveCapital"] = capital
        for src, dst in (("questionnaire_required", "required"), ("clinical_documentation_required", "documentationRequired")):
            flag = _as_bool(review.get(src))
            if flag is not None:
                questionnaire[dst] = flag
        settings["clinicalQuestionnaire"] = questionnaire

    renewal = snap.get("renewal.rules") or {}
    if renewal:
        indexation = dict(settings.get("capitalIndexation") or {})
        inflation = number(renewal.get("medical_inflation_percent"))
        if inflation is not None:
            indexation["medicalInflationPct"] = str(renewal["medical_inflation_percent"])
        if renewal.get("update_capitals") is not None or renewal.get("update_tables") is not None:
            indexation["reviewOnRenewal"] = bool(renewal.get("update_capitals") or renewal.get("update_tables"))
        settings["capitalIndexation"] = indexation
        settings["renewal"] = {
            "automatic": renewal.get("automatic_renewal"),
            "lossRatioAdjustment": renewal.get("loss_ratio_adjustment_enabled"),
            "continuityWithoutNewWaiting": renewal.get("continuity_without_new_waiting_period"),
        }
    if snap.get("renewal.deadlines"):
        settings["renewalDeadlines"] = dict(snap.get("renewal.deadlines") or {})

    network = snap.get("network.rules") or {}
    if network:
        settings["networkRules"] = dict(network)
        if network.get("pre_authorization_required") is True and not settings.get("priorAuthorization"):
            settings["priorAuthorization"] = {"internments": True, "highCostExams": True, "scheduledSurgeries": True}
    if snap.get("foreign_coverage.rules"):
        settings["foreignCoverage"] = dict(snap.get("foreign_coverage.rules") or {})
    if snap.rows("underwriting.acceptance_rules", "rules"):
        settings["acceptanceRules"] = snap.rows("underwriting.acceptance_rules", "rules")
    if snap.rows("underwriting.pre_existing_conditions", "rules"):
        settings["preExistingPolicy"] = snap.rows("underwriting.pre_existing_conditions", "rules")
    return settings


# ---------------------------------------------------------------- coverages
def _upsert_limit(limits: list[dict[str, Any]], kind: str, label: str | None, **fields: Any) -> None:
    for limit in limits:
        if limit.get("kind") == kind and (label is None or limit.get("label") in (None, label)):
            limit.update(fields)
            return
    limits.append({"kind": kind, **({"label": label} if label else {}), **fields})


def _apply_capital(cfg: dict[str, Any], row: dict[str, Any]) -> None:
    limits = [dict(x) for x in (cfg.get("limits") or [])]
    annual = _money(row.get("annual_capital"))
    if annual:
        primary = next((x for x in limits if x.get("kind") in _PRIMARY_KINDS), None)
        if primary:
            primary["amount"] = annual
        else:
            limits.append({"kind": "ANNUAL_PER_PERSON", "amount": annual})
    if _money(row.get("sublimit")):
        _upsert_limit(limits, "SUBLIMIT", "Sublimite", amount=_money(row["sublimit"]))
    if _money(row.get("per_event_limit")):
        _upsert_limit(limits, "PER_EVENT", None, amount=_money(row["per_event_limit"]))
    if _money(row.get("per_day_limit")):
        _upsert_limit(limits, "PER_ACT_OR_DAY", "Por dia", amount=_money(row["per_day_limit"]))
    quantity = integer(row.get("quantity_limit"))
    if quantity and quantity > 0:
        _upsert_limit(limits, "QUANTITY", "Quantidade", count=quantity)
    cfg["limits"] = limits


def _apply_participation(cfg: dict[str, Any], row: dict[str, Any], access_system: str | None) -> None:
    participation = {k: dict(v) for k, v in (cfg.get("participation") or {}).items()}
    blocks = {"NETWORK": ["NETWORK"], "REIMBURSEMENT": ["REIMBURSEMENT"]}.get(access_system or "", ["NETWORK", "REIMBURSEMENT"])
    copay, percent = _money(row.get("fixed_copayment")), number(row.get("reimbursement_percent"))
    for block in blocks:
        spec = participation.setdefault(block, {"type": "NONE"})
        if copay and block == "NETWORK":
            spec.update({"type": "COPAY_FIXED", "copayAmount": copay})
            spec.pop("insurerPct", None)
        elif percent is not None and 0 <= percent <= 100:
            spec.update({"type": "COINSURANCE", "insurerPct": str(row["reimbursement_percent"])})
            spec.pop("copayAmount", None)
            cap = _money(row.get("annual_cap"))
            if cap:
                spec["insuredAnnualCap"] = cap
        if _money(row.get("annual_deductible")):
            spec["annualDeductible"] = _money(row["annual_deductible"])
        if _money(row.get("event_deductible")):
            spec["perEventDeductible"] = _money(row["event_deductible"])
    cfg["participation"] = participation


def apply_coverage_overlay(
    *,
    plan,
    settings: dict[str, Any],
    coverages: dict[str, dict[str, Any]],
    benefits: dict[str, tuple[str, str | None, dict[str, Any] | None]],
    on: datetime.date | None = None,
    snapshot: BusinessSnapshot | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    """`benefits[code] = (name, category, definition)`. Devolve (configs, avisos)."""
    snap = snapshot or BusinessSnapshot.load(on)
    if not snap.values:
        return coverages, []

    warnings: list[dict[str, str]] = []
    out: dict[str, dict[str, Any]] = {}
    plan_rows = [r for r in snap.rows("product.plans", "plans") if matches_plan(r.get("code"), plan, settings)]
    default_copay = next((number(r.get("default_copayment_percent")) for r in plan_rows if r.get("default_copayment_percent") not in (None, "")), None)
    foreign = snap.get("foreign_coverage.rules") or {}

    for code, original in coverages.items():
        name, category, definition = benefits[code]
        definition = definition or {}
        cfg = copy.deepcopy(original)
        base_coverage = category == "BASE"

        for row in snap.rows("product.coverages", "coverages"):
            if not (matches_coverage(row.get("code"), code, name) or matches_coverage(row.get("name"), code, name)):
                continue
            if row.get("enabled") is False:
                if base_coverage:
                    warnings.append({"code": "BUSINESS_CONFIG_OVERLAY_REJECTED", "message": f"'{code}' é cobertura base e não pode ser desativada."})
                else:
                    cfg["inclusion"] = "UNAVAILABLE"
                continue
            listed = [p for p in (row.get("included_in_plans") or []) if p]
            if listed and any(matches_plan(p, plan, settings) for p in listed) and not base_coverage:
                cfg["inclusion"] = "OPTIONAL" if row.get("optional") is True else "INCLUDED"

        if cfg.get("inclusion") != "UNAVAILABLE":
            if default_copay is not None and not cfg.get("participation") and not definition.get("noParticipation") and 0 <= default_copay <= 100:
                _apply_participation(cfg, {"reimbursement_percent": 100 - default_copay}, settings.get("accessSystem"))
            for row in _generic_first(snap.rows("product.capitals_sublimits", "items")):
                if matches_plan(row.get("plan"), plan, settings) and matches_coverage(row.get("coverage"), code, name):
                    _apply_capital(cfg, row)
            for row in _generic_first(snap.rows("product.member_participation", "items")):
                if matches_plan(row.get("plan"), plan, settings) and matches_coverage(row.get("coverage"), code, name):
                    if definition.get("noParticipation"):
                        continue
                    _apply_participation(cfg, row, settings.get("accessSystem"))
            # Linhas sem plano primeiro, com plano depois: a última a bater
            # certo "ganha" (ver abaixo), por isso uma excepção específica de
            # plano nunca é atropelada por um valor geral da cobertura,
            # seja qual for a ordem em que o GTE as escreveu.
            waiting_rows = sorted(snap.rows("product.waiting_periods", "items"), key=lambda r: bool(r.get("plan")))
            for row in waiting_rows:
                if matches_plan(row.get("plan"), plan, settings) and matches_coverage(row.get("coverage"), code, name):
                    waiting = dict(cfg.get("waitingDays") or {})
                    individual, group = integer(row.get("individual_days")), integer(row.get("group_days"))
                    if individual is not None:
                        waiting["individual"] = individual
                    if group is not None:
                        waiting["group"] = group
                    if row.get("accident_exempt") is not None:
                        waiting["accidentWaived"] = bool(row["accident_exempt"])
                    cfg["waitingDays"] = waiting
            if code == "MEDICAL_EVACUATION" and foreign:
                if foreign.get("enabled") is False and not base_coverage:
                    cfg["inclusion"] = "UNAVAILABLE"
                else:
                    if foreign.get("countries"):
                        cfg["destinations"] = [str(c) for c in foreign["countries"]]
                    if _CURRENCY.get(str(foreign.get("currency") or "").upper()):
                        cfg["currency"] = _CURRENCY[str(foreign["currency"]).upper()]
                    if foreign.get("prior_approval") is not False:
                        cfg["requiresPriorApproval"] = True

        if cfg != original and cfg.get("inclusion") != "UNAVAILABLE":
            try:
                cfg, _ = validate_coverage_config(
                    cfg, benefit_code=code, benefit_category=category, benefit_definition=definition, plan_settings=settings
                )
            except DomainProblem as exc:
                warnings.append({"code": "BUSINESS_CONFIG_OVERLAY_REJECTED", "message": f"{code}: {exc}"})
                cfg = original
        out[code] = cfg
    return out, warnings


# -------------------------------------------------------------- exclusions
def effective_exclusions(plan, base: list[dict[str, Any]], on: datetime.date | None = None, snapshot: BusinessSnapshot | None = None) -> list[dict[str, Any]]:
    snap = snapshot or BusinessSnapshot.load(on)
    rows = snap.rows("product.exclusions", "items")
    if not rows:
        return [dict(x) for x in base]
    merged = {x["code"]: dict(x) for x in base}
    extra = 0
    for row in rows:
        applies = [p for p in (row.get("applies_to") or []) if p]
        if applies and not any(matches_plan(p, plan) for p in applies):
            continue
        code = str(row.get("code") or "").strip()
        if row.get("active") is False:
            merged.pop(code, None)
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        if not code:
            extra += 1
            code = f"BUSINESS_EXCLUSION_{extra}"
        merged[code] = {"code": code, "text": text, "productDependent": False, "source": "BUSINESS_CONFIG"}
    return list(merged.values())
