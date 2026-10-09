"""Projeção de sinistralidade em três cenários (R2): otimista, base, pessimista.

Método **simples e transparente** (`SIMPLE_TREND_V1`) — as fórmulas atuariais
do cliente ainda não foram fornecidas (OPEN_DECISIONS); quando o forem, o
método muda aqui sem mexer na API. Nada de percentagens por omissão: os
três cenários trazem as suas próprias premissas.

  janela        últimos 12 meses do histórico (ou os que existirem, com aviso)
  sinistros/ano = sinistros da janela × 12 / meses da janela
  prémio/ano    = prémio ganho da janela × 12 / meses da janela
  escala vidas  = projectedInsured / média de pessoas da janela (se indicado;
                  escala sinistros e prémio por igual)
  crescimento   = ((1 + inflação/100) × (1 + tendência de frequência/100)) ^ (horizonte/12)
  sinistros proj. = sinistros/ano × escala × crescimento
  loss ratio esperado = sinistros proj. / (prémio/ano × escala) × 100
  prémio necessário   = sinistros proj. / (alvo/100)
  impacto no prémio   = prémio necessário / (prémio/ano × escala) − 1
"""
from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.claims.application import summary_service
from apps.claims.infrastructure.models import ProjectionAssumptionSet, ProjectionRun
from apps.client.infrastructure.models import Proposer
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter

_audit = AuditService(DjangoAuditRepositoryAdapter())
SCENARIOS = ("OPTIMISTIC", "BASE", "PESSIMISTIC")
METHOD = "SIMPLE_TREND_V1"
TWO = Decimal("0.01")


class InvalidProjectionError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class ProjectionNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


class DuplicateAssumptionSetError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


def _dec(raw: Any, path: str, *, minimum: str = "-100", maximum: str = "1000") -> Decimal:
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise InvalidProjectionError(f"{path} tem de ser um decimal escrito como texto")
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise InvalidProjectionError(f"{path} não é um decimal válido") from exc
    if not value.is_finite() or value < Decimal(minimum) or value > Decimal(maximum):
        raise InvalidProjectionError(f"{path} tem de estar entre {minimum} e {maximum}")
    return value


def validate_params(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InvalidProjectionError("assumptions tem de ser um objeto")
    allowed = {"horizonMonths", "targetLossRatioPct", "projectedInsured", "scenarios", "windowMonths"}
    if set(raw) - allowed:
        raise InvalidProjectionError(f"Pressuposto(s) desconhecido(s): {sorted(set(raw) - allowed)}")
    horizon = raw.get("horizonMonths")
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 60:
        raise InvalidProjectionError("horizonMonths tem de ser um número inteiro entre 1 e 60")
    window = raw.get("windowMonths", 12)
    if isinstance(window, bool) or not isinstance(window, int) or not 1 <= window <= 60:
        raise InvalidProjectionError("windowMonths tem de ser um número inteiro entre 1 e 60")
    target = _dec(raw.get("targetLossRatioPct"), "targetLossRatioPct", minimum="1", maximum="100")
    params: dict[str, Any] = {"horizonMonths": horizon, "windowMonths": window, "targetLossRatioPct": str(target)}
    if raw.get("projectedInsured") is not None:
        insured = raw["projectedInsured"]
        if isinstance(insured, bool) or not isinstance(insured, int) or insured < 1:
            raise InvalidProjectionError("projectedInsured tem de ser um número inteiro positivo")
        params["projectedInsured"] = insured
    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, dict) or set(scenarios) != set(SCENARIOS):
        raise InvalidProjectionError(f"scenarios tem de definir exatamente {list(SCENARIOS)} (não se assumem valores por omissão)")
    parsed: dict[str, dict[str, str]] = {}
    for name in SCENARIOS:
        spec = scenarios[name]
        if not isinstance(spec, dict):
            raise InvalidProjectionError(f"scenarios.{name} tem de ser um objeto")
        parsed[name] = {
            "medicalInflationPct": str(_dec(spec.get("medicalInflationPct"), f"scenarios.{name}.medicalInflationPct")),
            "frequencyTrendPct": str(_dec(spec.get("frequencyTrendPct"), f"scenarios.{name}.frequencyTrendPct")),
        }
    for key in ("medicalInflationPct", "frequencyTrendPct"):
        values = [Decimal(parsed[n][key]) for n in SCENARIOS]
        if not values[0] <= values[1] <= values[2]:
            raise InvalidProjectionError(f"{key} tem de cumprir OPTIMISTIC <= BASE <= PESSIMISTIC")
    params["scenarios"] = parsed
    return params


def _q(value: Decimal) -> str:
    return str(value.quantize(TWO))


def project(*, proposer_id, params: dict[str, Any], policy_id=None, currency: str = "AOA") -> dict[str, Any]:
    months_available = summary_service.history_months(proposer_id=proposer_id, currency=currency)
    if months_available == 0:
        raise InvalidProjectionError(f"Não há histórico importado para este cliente em {currency}")
    # window ends at the last month with data
    probe = summary_service.summary(proposer_id=proposer_id, policy_id=policy_id, currency=currency, record_audit=False)
    end = datetime.date.fromisoformat(probe["period"]["to"])
    window = min(params["windowMonths"], months_available)
    start_month = (end.year * 12 + end.month - 1) - (window - 1)
    start = datetime.date(start_month // 12, start_month % 12 + 1, 1)
    base = summary_service.summary(
        proposer_id=proposer_id, policy_id=policy_id, date_from=start, date_to=end, currency=currency, record_audit=True
    )
    claims_total = Decimal(base["claims"]["total"])
    earned = Decimal(base["premium"]["earned"])
    if earned <= 0:
        raise InvalidProjectionError("A projeção precisa de prémio adquirido na janela (importe também os prémios)")
    warnings = []
    if window < params["windowMonths"]:
        warnings.append(f"Só existem {window} meses de histórico (pedidos {params['windowMonths']}).")
    if window < 12:
        warnings.append("Menos de 12 meses de histórico: a projeção anualizada é pouco fiável.")

    annual_factor = Decimal(12) / Decimal(window)
    annual_claims = claims_total * annual_factor
    annual_premium = earned * annual_factor
    scale = Decimal("1")
    if params.get("projectedInsured"):
        years = base["premium"]["insuredYears"]
        if years is None:
            raise InvalidProjectionError("projectedInsured precisa de insured_count nos prémios importados")
        avg_insured = Decimal(years) / (Decimal(window) / Decimal(12))
        scale = Decimal(params["projectedInsured"]) / avg_insured
    target = Decimal(params["targetLossRatioPct"])
    horizon = params["horizonMonths"]
    base_premium = annual_premium * scale

    scenarios: dict[str, Any] = {}
    for name in SCENARIOS:
        spec = params["scenarios"][name]
        growth_year = (Decimal(1) + Decimal(spec["medicalInflationPct"]) / 100) * (Decimal(1) + Decimal(spec["frequencyTrendPct"]) / 100)
        growth = growth_year ** (Decimal(horizon) / Decimal(12))
        projected = annual_claims * scale * growth
        required = projected / (target / Decimal(100))
        monthly = [
            {"month": m, "expectedClaims": _q(annual_claims * scale / Decimal(12) * (growth_year ** (Decimal(m) / Decimal(12))))}
            for m in range(1, horizon + 1)
        ]
        scenarios[name] = {
            "medicalInflationPct": spec["medicalInflationPct"],
            "frequencyTrendPct": spec["frequencyTrendPct"],
            "growthFactor": str(growth.quantize(Decimal("0.0001"))),
            "projectedClaims": _q(projected),
            "expectedLossRatioPct": _q(projected / base_premium * Decimal("100")),
            "requiredPremium": _q(required),
            "premiumImpactPct": _q((required / base_premium - Decimal(1)) * Decimal("100")),
            "monthly": monthly,
        }
    return {
        "method": METHOD,
        "methodNote": "Método simples de tendência; as fórmulas atuariais do cliente ainda não foram confirmadas.",
        "proposerId": str(proposer_id),
        "currencyCode": currency,
        "window": {"from": start.isoformat(), "to": end.isoformat(), "months": window},
        "history": {
            "claimsTotal": base["claims"]["total"], "earnedPremium": base["premium"]["earned"],
            "lossRatioPct": base["lossRatioPct"], "claimsCount": base["claims"]["count"],
        },
        "annualized": {"claims": _q(annual_claims * scale), "premium": _q(base_premium), "livesScale": str(scale.quantize(Decimal("0.0001")))},
        "targetLossRatioPct": params["targetLossRatioPct"],
        "horizonMonths": horizon,
        "scenarios": scenarios,
        "warnings": warnings,
    }


# ------------------------------------------------------- persistence
def create_assumption_set(*, name: str, params: dict[str, Any]) -> ProjectionAssumptionSet:
    clean = validate_params(params)
    actor = CurrentActorProvider.get()
    from django.db import IntegrityError, transaction

    try:
        with transaction.atomic():
            created = ProjectionAssumptionSet.objects.create(
                tenant_id=CurrentTenantProvider.require().value, name=name, params_json=clean,
                created_by=actor.actor_id if actor else "unknown",
            )
    except IntegrityError as exc:
        raise DuplicateAssumptionSetError(f"Já existe um conjunto de pressupostos com o nome '{name}'") from exc
    _audit.record(
        action="claims.assumption_set_created", entity_type="ProjectionAssumptionSet", entity_id=str(created.id),
        metadata=change_metadata(after={"name": name, "params": clean}),
    )
    return created


def get_assumption_set(set_id) -> ProjectionAssumptionSet:
    obj = ProjectionAssumptionSet.objects.filter(id=set_id).first()
    if obj is None:
        raise ProjectionNotFoundError(f"O conjunto de pressupostos {set_id} não existe")
    return obj


def run_projection(*, proposer_id, policy_id, assumption_set_id, assumptions: dict | None, currency: str) -> ProjectionRun:
    if not Proposer.objects.filter(id=proposer_id).exists():
        raise InvalidProjectionError(f"O cliente (proposerId) {proposer_id} não existe neste tenant")
    assumption_set = get_assumption_set(assumption_set_id) if assumption_set_id else None
    if assumption_set is None and assumptions is None:
        raise InvalidProjectionError("Indique assumptionSetId ou assumptions")
    params = assumption_set.params_json if assumption_set else validate_params(assumptions)
    result = project(proposer_id=proposer_id, params=params, policy_id=policy_id, currency=currency)
    actor = CurrentActorProvider.get()
    run = ProjectionRun.objects.create(
        tenant_id=CurrentTenantProvider.require().value, proposer_id=proposer_id, policy_id=policy_id,
        assumption_set=assumption_set, params_json=params, result_json=result, created_by=actor.actor_id if actor else "unknown",
    )
    _audit.record(
        action="claims.projection_run", entity_type="ProjectionRun", entity_id=str(run.id),
        metadata=change_metadata(after={"params": params}, proposerId=str(proposer_id)),
    )
    return run


def get_run(run_id) -> ProjectionRun:
    run = ProjectionRun.objects.filter(id=run_id).first()
    if run is None:
        raise ProjectionNotFoundError(f"A projeção {run_id} não existe")
    return run


def methodology() -> dict[str, Any]:
    """Descrição transparente do método em uso, para a interface e para o
    negócio validarem. É **indicativo** até as fórmulas atuariais do cliente
    serem confirmadas (então muda aqui, sem alterar a API)."""
    from apps.claims.application.import_service import IMPORT_FORMATS

    return {
        "method": METHOD,
        "indicative": True,
        "note": "Método simples de tendência; as fórmulas atuariais do cliente ainda não foram confirmadas.",
        "formulas": [line.strip() for line in (__doc__ or "").splitlines() if "=" in line],
        "assumptionsRequired": ["inflationPct", "frequencyTrendPct", "horizonMonths", "targetLossRatioPct"],
        "scenarios": list(SCENARIOS),
        "importFormats": IMPORT_FORMATS,
        "dateFormats": ["YYYY-MM-DD", "DD/MM/YYYY"],
        "currencies": ["AOA", "USD"],
    }
