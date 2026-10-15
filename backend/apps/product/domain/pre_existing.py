"""Decisão de subscrição sobre uma doença preexistente (por pessoa segura).

PDF "Exclusões e doenças preexistentes": as doenças preexistentes são
excluídas no seguro individual, salvo aceitação expressa após questionário
clínico, e em regra aceites nos grupos com adesão obrigatória. Seis
tratamentos, cada um com o seu âmbito de aplicação:

  TOTAL_EXCLUSION         Exclusão total — Individual, padrão
  SPECIFIC_EXCLUSION      Exclusão específica — Individual, após análise médica
  ACCEPTED_WITH_WAITING   Aceitação com carência (12 a 24 meses) — Individual Superior
  ACCEPTED_WITH_LOADING   Aceitação com sobreprémio — Individual, casos selecionados
  ACCEPTED_WITH_SUBLIMIT  Aceitação com sublimite — Grupo e Individual
  FULL_ACCEPTANCE         Aceitação integral — Grupo com adesão obrigatória

A decisão fica na linha do membro da cotação (`quote_member.pre_existing_json`)
e alimenta o preço (sobreprémio), a proposta (exclusões/carência/sublimite)
e a auditoria.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.foundation.domain.problem import DomainProblem
from apps.product.domain.plan_settings import PRE_EXISTING_MODES, decimal_value

_INDIVIDUAL_MODES = (
    "TOTAL_EXCLUSION", "SPECIFIC_EXCLUSION", "ACCEPTED_WITH_WAITING", "ACCEPTED_WITH_LOADING", "ACCEPTED_WITH_SUBLIMIT",
)


# Tratamentos da configuração de negócio (`underwriting.pre_existing_conditions`)
# e o modo de decisão que cada um produz.
BUSINESS_TREATMENT_MODE = {
    "EXCLUSION_TOTAL": "TOTAL_EXCLUSION",
    "EXCLUSION_SPECIFIC": "SPECIFIC_EXCLUSION",
    "WAITING_PERIOD": "ACCEPTED_WITH_WAITING",
    "SURCHARGE": "ACCEPTED_WITH_LOADING",
    "SUBLIMIT": "ACCEPTED_WITH_SUBLIMIT",
    "FULL_ACCEPTANCE": "FULL_ACCEPTANCE",
}


class InvalidPreExistingDecisionError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _err(message: str) -> InvalidPreExistingDecisionError:
    return InvalidPreExistingDecisionError(message)


def validate_pre_existing_decision(
    raw: Any, *, plan_settings: dict[str, Any] | None
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    settings = plan_settings or {}
    segment = settings.get("segment")
    adhesion = (settings.get("group") or {}).get("adhesion")
    warnings: list[dict[str, str]] = []

    if not isinstance(raw, dict):
        raise _err("decision tem de ser um objeto")
    raw = dict(raw)
    mode = raw.get("mode")
    if mode not in PRE_EXISTING_MODES:
        raise _err(f"mode tem de ser um de {list(PRE_EXISTING_MODES)}")

    # Política de negócio por gravidade: restringe os tratamentos permitidos
    # e fornece os valores por omissão (carência, sobreprémio, sublimite).
    severity = raw.get("severity")
    policy = [r for r in (settings.get("preExistingPolicy") or []) if isinstance(r, dict)]
    if policy:
        if severity is None:
            raise _err("severity (LOW, MODERATE, MODERATE_HIGH ou HIGH) é obrigatória: o negócio definiu tratamentos por gravidade")
        rules = [r for r in policy if r.get("severity") == severity]
        if not rules:
            raise _err(f"O negócio não definiu tratamento para a gravidade '{severity}'")
        allowed = {BUSINESS_TREATMENT_MODE.get(r.get("treatment")) for r in rules}
        if mode not in allowed:
            raise _err(f"Para gravidade {severity} o negócio só permite: {sorted(m for m in allowed if m)}")
        rule = next(r for r in rules if BUSINESS_TREATMENT_MODE.get(r.get("treatment")) == mode)
        if mode == "ACCEPTED_WITH_WAITING" and raw.get("waitingMonths") is None and rule.get("waiting_days"):
            raw["waitingMonths"] = max(12, min(24, round(float(rule["waiting_days"]) / 30)))
        if mode == "ACCEPTED_WITH_LOADING" and raw.get("loadingPct") is None and rule.get("surcharge_percent") is not None:
            raw["loadingPct"] = rule["surcharge_percent"]
        if mode == "ACCEPTED_WITH_SUBLIMIT" and raw.get("sublimitAmount") is None and rule.get("sublimit"):
            raw["sublimitAmount"] = rule["sublimit"]

    if segment == "INDIVIDUAL_FAMILY" and mode not in _INDIVIDUAL_MODES:
        raise _err(f"{mode} só se aplica a planos GROUP com adesão obrigatória")
    if segment == "GROUP":
        if mode == "FULL_ACCEPTANCE" and adhesion != "MANDATORY":
            raise _err("FULL_ACCEPTANCE só se aplica a planos GROUP com adesão obrigatória (MANDATORY)")
        if mode in ("SPECIFIC_EXCLUSION", "ACCEPTED_WITH_WAITING", "ACCEPTED_WITH_LOADING"):
            raise _err(f"{mode} é um tratamento do seguro individual; um plano GROUP aceita com sublimite ou na totalidade")
        if mode == "TOTAL_EXCLUSION" and adhesion == "MANDATORY":
            raise _err("Um plano GROUP com adesão obrigatória aceita doenças preexistentes (com sublimite ou na totalidade)")

    decision: dict[str, Any] = {"mode": mode}
    if severity is not None:
        decision["severity"] = severity
    if mode == "ACCEPTED_WITH_WAITING":
        months = raw.get("waitingMonths")
        if isinstance(months, bool) or not isinstance(months, int) or not 12 <= months <= 24:
            raise _err("waitingMonths tem de ser um número inteiro entre 12 e 24")
        decision["waitingMonths"] = months
        if segment == "INDIVIDUAL_FAMILY" and settings.get("tier") != "SUPERIOR":
            warnings.append(
                {"code": "PRE_EXISTING_WAITING_TIER", "message": "Aceitação com carência aplica-se tipicamente ao Individual Superior."}
            )
    if mode == "ACCEPTED_WITH_LOADING":
        try:
            decision["loadingPct"] = str(decimal_value(raw.get("loadingPct"), "loadingPct", minimum=Decimal("0.01"), maximum=Decimal("1000")))
        except DomainProblem as exc:
            raise _err(str(exc)) from exc
    if mode == "ACCEPTED_WITH_SUBLIMIT":
        try:
            decision["sublimitAmount"] = str(decimal_value(raw.get("sublimitAmount"), "sublimitAmount", minimum=Decimal("0.01")))
        except DomainProblem as exc:
            raise _err(str(exc)) from exc
    if mode == "SPECIFIC_EXCLUSION":
        condition = (raw.get("condition") or "").strip() if isinstance(raw.get("condition"), str) else ""
        if not condition:
            raise _err("SPECIFIC_EXCLUSION exige a doença declarada ('condition')")
        decision["condition"] = condition
    elif isinstance(raw.get("condition"), str) and raw["condition"].strip():
        decision["condition"] = raw["condition"].strip()

    # PDF: sem questionário clínico não há aceitação expressa no individual.
    if segment == "INDIVIDUAL_FAMILY" and mode != "TOTAL_EXCLUSION" and not raw.get("clinicalQuestionnaireCompleted"):
        raise _err("aceitar uma doença preexistente no seguro individual exige o questionário clínico (clinicalQuestionnaireCompleted=true)")
    if raw.get("clinicalQuestionnaireCompleted"):
        decision["clinicalQuestionnaireCompleted"] = True
    return decision, warnings
