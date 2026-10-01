"""Configuração de uma cobertura num plano (`PlanBenefit.configuration_json`).

Cobre, do PDF "Seguro de Saúde — Coberturas e Capitais" (1-Out-2026):
  - **inclusão**: B (`INCLUDED`) ou O (`OPTIONAL`); "—" é não estar associada;
  - **formas de garantia dos capitais**: capital anual por pessoa, capital
    por agregado/partilhado, sublimite, limite por ato/dia, limite de
    quantidade, percentagem de comparticipação, capital fixo (forfetário),
    capital por evento, bienal, por serviço — e a regra "sem rateio";
  - **participação do segurado** por sistema de acesso (rede convencionada /
    reembolso): sem participação, copagamento fixo por ato, comparticipação
    parcial (co-seguro) e comparticipação com máximo anual, mais franquia
    anual e franquia por evento;
  - **carências** (individual/grupo, acidente dispensa, cirurgias programadas);
  - **moeda por cobertura** (Kz ou USD, p.ex. evacuação) e aprovação prévia.

Como em `plan_settings`, devolve `(config, warnings)`; um erro recusa a
gravação, um aviso é uma recomendação do PDF que o GTE pode aceitar.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.foundation.domain.problem import DomainProblem
from apps.product.domain.market_catalog import GUARANTEE_FORMS
from apps.product.domain.plan_settings import decimal_value

INCLUSIONS = ("INCLUDED", "OPTIONAL")
PARTICIPATION_TYPES = ("NONE", "COPAY_FIXED", "COINSURANCE")
ACCESS_BLOCKS = ("NETWORK", "REIMBURSEMENT")

# Capital "principal" de uma cobertura (no máximo um, salvo vários capitais
# por evento com rótulos distintos — ex. parto normal / cesariana).
_SINGLE_PRIMARY_KINDS = ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED", "BIENNIAL", "FIXED_AMOUNT")
_EVENT_KIND = "PER_EVENT"
_SUB_KINDS = ("SUBLIMIT", "PER_ACT_OR_DAY", "PER_SERVICE")
_AMOUNT_KINDS = (*_SINGLE_PRIMARY_KINDS, _EVENT_KIND, *_SUB_KINDS)
_CAP_KINDS = ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED", "BIENNIAL")

_ALLOWED_KEYS = {
    "inclusion", "currency", "limits", "participation", "waitingDays", "requiresPriorApproval", "maxDaysPerYear",
    "timeDeductibleDays", "destinations", "closedDiseaseList", "excludedItems", "exclusions", "notes", "indicative",
    "mandatoryInEveryPlan",
}


class InvalidCoverageConfigError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _err(message: str) -> InvalidCoverageConfigError:
    return InvalidCoverageConfigError(message)


def _dec(raw: Any, path: str, **kwargs: Any) -> Decimal:
    try:
        return decimal_value(raw, path, **kwargs)
    except DomainProblem as exc:  # re-raise with this module's error type
        raise _err(str(exc)) from exc


def _int(raw: Any, path: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise _err(f"{path} must be an integer")
    if raw < minimum or (maximum is not None and raw > maximum):
        raise _err(f"{path} must be between {minimum} and {maximum if maximum is not None else '∞'}")
    return raw


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_coverage_config(
    raw: Any,
    *,
    benefit_code: str,
    benefit_category: str | None,
    benefit_definition: dict[str, Any] | None,
    plan_settings: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    definition = benefit_definition or {}
    settings = plan_settings or {}
    segment = settings.get("segment")
    access_system = settings.get("accessSystem")
    warnings: list[dict[str, str]] = []

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _err("configuration must be an object")
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        raise _err(f"Unknown coverage configuration key(s): {sorted(unknown)}")

    config: dict[str, Any] = dict(raw)

    # ---- inclusão (B/O)
    inclusion = config.get("inclusion", "INCLUDED")
    if inclusion not in INCLUSIONS:
        raise _err(f"inclusion must be one of {list(INCLUSIONS)} (a coverage that is not available is simply not attached)")
    if benefit_category == "BASE" and inclusion != "INCLUDED":
        raise _err(f"'{benefit_code}' is a mandatory (BASE) coverage: it must be INCLUDED in every plan")
    config["inclusion"] = inclusion

    # ---- moeda (Kz ou USD, só onde a cobertura o permite)
    allowed_currencies = definition.get("allowedCurrencies") or ["AOA"]
    currency = config.get("currency") or settings.get("currency") or "AOA"
    if currency not in ("AOA", "USD"):
        raise _err("currency must be AOA or USD")
    if currency not in allowed_currencies:
        raise _err(f"currency '{currency}' is not allowed for '{benefit_code}' (allowed: {allowed_currencies})")
    config["currency"] = currency
    if currency == "USD":
        warnings.append(_warning("FX_RISK", "Capital em USD: considerar o risco cambial e a moeda do capital."))

    # ---- limites / capitais
    limits = config.get("limits", [])
    if not isinstance(limits, list):
        raise _err("limits must be a list")
    primary_amount: Decimal | None = None
    cap_seen: dict[str, int] = {}
    event_labels: set[str] = set()
    coinsurance_seen = False
    parsed_limits: list[dict[str, Any]] = []
    for idx, limit in enumerate(limits):
        path = f"limits[{idx}]"
        if not isinstance(limit, dict):
            raise _err(f"{path} must be an object")
        kind = limit.get("kind")
        if kind not in GUARANTEE_FORMS and kind != "COINSURANCE_PCT":
            raise _err(f"{path}.kind must be one of {sorted(GUARANTEE_FORMS)}")
        entry = dict(limit)
        if kind in _SUB_KINDS or kind == _EVENT_KIND:
            if not limit.get("label") and kind != _EVENT_KIND:
                raise _err(f"{path}.label is required for a {kind} limit")
        if kind in _AMOUNT_KINDS:
            entry["_amount"] = _dec(limit.get("amount"), f"{path}.amount", minimum=Decimal("0.01"))
        if kind == "QUANTITY":
            _int(limit.get("count"), f"{path}.count", minimum=1)
            if not limit.get("label"):
                raise _err(f"{path}.label is required for a QUANTITY limit")
        if kind == "COINSURANCE_PCT":
            if coinsurance_seen:
                raise _err("Only one COINSURANCE_PCT limit is allowed")
            coinsurance_seen = True
            _dec(limit.get("pct"), f"{path}.pct", minimum=Decimal("0.01"), maximum=Decimal("100"))
        if kind in _SINGLE_PRIMARY_KINDS:
            cap_seen[kind] = cap_seen.get(kind, 0) + 1
        if kind == _EVENT_KIND:
            label = limit.get("label") or "default"
            if label in event_labels:
                raise _err(f"{path}: duplicate PER_EVENT label '{label}'")
            event_labels.add(label)
        if kind == "HOUSEHOLD_SHARED" and segment == "GROUP":
            raise _err("HOUSEHOLD_SHARED capital (one capital for the whole family) only applies to INDIVIDUAL_FAMILY plans")
        if kind in _CAP_KINDS and "_amount" in entry:
            primary_amount = entry["_amount"]
        parsed_limits.append(entry)
    if sum(cap_seen.values()) > 1:
        raise _err(
            "A coverage has a single main capital (ANNUAL_PER_PERSON, HOUSEHOLD_SHARED, BIENNIAL or FIXED_AMOUNT); "
            "use SUBLIMIT/PER_ACT_OR_DAY/QUANTITY for limits inside it"
        )
    for entry in parsed_limits:
        if entry["kind"] in ("SUBLIMIT", "PER_ACT_OR_DAY") and primary_amount is not None and entry["_amount"] > primary_amount:
            raise _err(f"Sublimit '{entry.get('label')}' cannot exceed the coverage capital ({primary_amount})")
        entry.pop("_amount", None)
    config["limits"] = parsed_limits

    if not parsed_limits and inclusion == "INCLUDED" and benefit_code != "ASSISTANCE_24H":
        warnings.append(_warning("NO_CAPITAL", f"'{benefit_code}' não tem capital/limite definido."))

    # ---- participação por sistema de acesso
    participation = config.get("participation", {})
    if not isinstance(participation, dict):
        raise _err("participation must be an object")
    if set(participation) - set(ACCESS_BLOCKS):
        raise _err(f"participation keys must be within {list(ACCESS_BLOCKS)}")
    for block, spec in participation.items():
        path = f"participation.{block}"
        if not isinstance(spec, dict):
            raise _err(f"{path} must be an object")
        ptype = spec.get("type", "NONE")
        if ptype not in PARTICIPATION_TYPES:
            raise _err(f"{path}.type must be one of {list(PARTICIPATION_TYPES)}")
        if ptype == "COPAY_FIXED":
            if block != "NETWORK":
                raise _err(f"{path}: a fixed copayment is paid to the provider in the agreed network (NETWORK only)")
            _dec(spec.get("copayAmount"), f"{path}.copayAmount", minimum=Decimal("0.01"))
        if ptype == "COINSURANCE":
            _dec(spec.get("insurerPct"), f"{path}.insurerPct", maximum=Decimal("100"))
            if spec.get("insuredAnnualCap") is not None:
                _dec(spec["insuredAnnualCap"], f"{path}.insuredAnnualCap")
        if ptype != "COINSURANCE" and spec.get("insuredAnnualCap") is not None:
            raise _err(f"{path}.insuredAnnualCap (annual ceiling) only applies to COINSURANCE")
        if ptype == "NONE" and (spec.get("copayAmount") is not None or spec.get("insurerPct") is not None):
            raise _err(f"{path}: type NONE (no participation) cannot carry copayAmount/insurerPct")
        for field in ("annualDeductible", "perEventDeductible"):
            if spec.get(field) is not None:
                _dec(spec[field], f"{path}.{field}")
        if definition.get("noParticipation") and (ptype != "NONE" or spec.get("annualDeductible") or spec.get("perEventDeductible")):
            raise _err(f"'{benefit_code}' is paid in full by the insurer (no participation)")
    if access_system == "NETWORK" and "REIMBURSEMENT" in participation:
        warnings.append(_warning("ACCESS_SYSTEM_MISMATCH", "O plano é só de rede convencionada: o bloco de reembolso será ignorado."))
    if access_system == "REIMBURSEMENT" and "NETWORK" in participation:
        warnings.append(_warning("ACCESS_SYSTEM_MISMATCH", "O plano é só de reembolso: o bloco de rede será ignorado."))
    if access_system == "MIXED" and inclusion == "INCLUDED" and participation and set(participation) != set(ACCESS_BLOCKS):
        warnings.append(
            _warning("MIXED_NEEDS_BOTH", "Sistema misto: definir a participação na rede e no reembolso (fora da rede ou no estrangeiro).")
        )
    if benefit_code == "MEDICAL_EVACUATION":
        network = participation.get("NETWORK", {})
        if network and network.get("type", "NONE") != "NONE":
            warnings.append(_warning("EVACUATION_PARTICIPATION", "Evacuação aprovada é paga sem participação (0% se aprovada)."))

    # ---- carências
    waiting = config.get("waitingDays", {})
    if not isinstance(waiting, dict):
        raise _err("waitingDays must be an object")
    for key in ("individual", "group", "scheduledSurgery"):
        if key in waiting:
            _int(waiting[key], f"waitingDays.{key}", maximum=3650)
    if "accidentWaived" in waiting and not isinstance(waiting["accidentWaived"], bool):
        raise _err("waitingDays.accidentWaived must be a boolean")
    if segment == "INDIVIDUAL_FAMILY" and definition.get("antiSelectionWaiting") and not waiting.get("individual"):
        warnings.append(
            _warning(
                "ANTI_SELECTION",
                f"Carência recomendada em '{benefit_code}' no individual: evita adesões apenas para despesas previstas (anti-seleção).",
            )
        )
    group_rules = settings.get("waitingRules", {}) if isinstance(settings.get("waitingRules"), dict) else {}
    if segment == "GROUP" and group_rules.get("groupMandatoryEliminatesWaiting") and waiting.get("group"):
        warnings.append(_warning("GROUP_WAITING", "Na adesão obrigatória de grupos é comum eliminar as carências."))
    config["waitingDays"] = waiting

    # ---- aprovação prévia (evacuação sem aprovação prévia é exclusão)
    if "requiresPriorApproval" in config and not isinstance(config["requiresPriorApproval"], bool):
        raise _err("requiresPriorApproval must be a boolean")
    if definition.get("requiresPriorApproval") and config.get("requiresPriorApproval") is False:
        raise _err(f"'{benefit_code}' requires prior approval (treatment abroad without prior approval is excluded)")
    if definition.get("requiresPriorApproval"):
        config["requiresPriorApproval"] = True

    # ---- campos específicos
    if "destinations" in config:
        destinations = config["destinations"]
        if not isinstance(destinations, list) or not all(isinstance(d, str) and d for d in destinations):
            raise _err("destinations must be a list of names")
    elif benefit_code == "MEDICAL_EVACUATION" and inclusion == "INCLUDED":
        warnings.append(_warning("EVACUATION_DESTINATIONS", "Definir os destinos da evacuação (ex.: Portugal, África do Sul, Brasil, Namíbia)."))
    if "closedDiseaseList" in config:
        diseases = config["closedDiseaseList"]
        if not isinstance(diseases, list) or not diseases or not all(isinstance(d, str) and d for d in diseases):
            raise _err("closedDiseaseList must be a non-empty list (lista fechada de doenças)")
    elif benefit_code == "CRITICAL_ILLNESS":
        warnings.append(_warning("CLOSED_LIST", "Doenças graves: definir a lista fechada de doenças."))
    if "maxDaysPerYear" in config:
        days = _int(config["maxDaysPerYear"], "maxDaysPerYear", minimum=1, maximum=365)
        if days not in (30, 60):
            warnings.append(_warning("ALLOWANCE_DAYS", "Máximo de dias por ano típico do subsídio de internamento: 30 ou 60."))
    elif benefit_code == "HOSPITAL_DAILY_ALLOWANCE":
        warnings.append(_warning("ALLOWANCE_DAYS", "Subsídio de internamento: definir o máximo de dias por ano (ex.: 30 ou 60)."))
    if "timeDeductibleDays" in config:
        _int(config["timeDeductibleDays"], "timeDeductibleDays", maximum=30)
    for key in ("excludedItems", "exclusions"):
        if key in config and not isinstance(config[key], list):
            raise _err(f"{key} must be a list")

    return config, warnings


def plan_completeness_issues(
    *,
    segment: str | None,
    coverages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Plan-level checks over all attached coverages (`coverages` items:
    `{code, category, config}`) — used by `GET /plans/{id}/validation`.
    Returns issues with `severity` ERROR/WARNING."""
    issues: list[dict[str, str]] = []
    by_code = {c["code"]: c for c in coverages}

    def issue(severity: str, code: str, message: str) -> None:
        issues.append({"severity": severity, "code": code, "message": message})

    hospital = by_code.get("HOSPITALIZATION")
    if hospital is None:
        issue("ERROR", "HOSPITALIZATION_MISSING", "A hospitalização é a cobertura base obrigatória de todo o plano.")
    elif not any(lim.get("kind") == "ANNUAL_PER_PERSON" for lim in hospital["config"].get("limits", [])):
        issue("ERROR", "HOSPITALIZATION_CAPITAL", "Hospitalização: definir o capital anual por pessoa segura.")
    for code in ("AMBULATORY_SURGERY", "EMERGENCY"):
        if code not in by_code:
            issue("ERROR", f"{code}_MISSING", f"'{code}' está em todos os planos (B em todas as colunas do PDF).")
    outpatient = by_code.get("OUTPATIENT")
    if outpatient is not None and outpatient["config"].get("inclusion") == "INCLUDED":
        limits = outpatient["config"].get("limits", [])
        if not any(lim.get("kind") in ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED") for lim in limits):
            issue("WARNING", "OUTPATIENT_CAPITAL", "Ambulatório: definir o capital anual (por pessoa ou por agregado) e os sublimites por consulta.")
    return issues
