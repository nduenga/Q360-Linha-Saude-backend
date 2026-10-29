"""Tarifa de um produto, pela ordem em que o motor a aplica, e simulação
de rascunhos antes de os submeter.

A tarifa segue a cascata seguradora → produto → plano (`domain/scope.py`):
cada chave `pricing.*`, `rules.custom`, `product.minimum_premium`… tem uma
versão geral e pode ter uma versão do produto (`<chave>@<produto>`), que a
substitui nesse produto; o plano entra como dimensão dentro delas.
`pricing.taxes_fees` fica sempre geral e `product.pricing_setup:<produto>` é
só deste produto. Este módulo junta-as numa vista por passo, com o estado de
cada versão, de onde vem o valor em uso e o dono de cada passo: CODE (o
motor), PLATFORM (o fornecedor) ou TENANT (a seguradora).

A simulação corre o cálculo real de uma cotação de exemplo, numa transação
que é sempre revertida: os rascunhos escolhidos passam a valer só dentro
dela, e nada fica gravado (nem a cotação, nem as pessoas, nem o cálculo)."""
from __future__ import annotations

import datetime
import secrets
from typing import Any

from django.db import models, transaction
from django.utils import timezone

from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.product_setup import config_key as product_setup_key
from apps.business_config.domain.scope import is_scopable, product_key
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.application import platform_parameter_service
from apps.foundation.domain.problem import DomainProblem

CODE, PLATFORM, TENANT = "CODE", "PLATFORM", "TENANT"
OPEN_STATUSES = ("DRAFT", "REJECTED", "PENDING_APPROVAL")
FREQUENCIES = {"ANUAL": 1, "SEMESTRAL": 2, "TRIMESTRAL": 4, "MENSAL": 12}
MAX_SIMULATED_MEMBERS = 50


class TariffSimulationError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _stages(product_id) -> list[dict[str, Any]]:
    setup_key = product_setup_key(product_id)
    return [
        {"code": "PURE_PREMIUM", "label": "Prémio puro por idade, sexo e cobertura", "owner": TENANT,
         "configKeys": ["pricing.actuarial_model", "pricing.reference_premiums"]},
        {"code": "RISK_FACTORS", "label": "Fatores de risco", "owner": TENANT, "configKeys": ["pricing.factors"]},
        {"code": "PERSON_RULES", "label": "Regras por pessoa e pré-existências", "owner": TENANT,
         "configKeys": ["rules.custom", "underwriting.pre_existing_conditions"]},
        {"code": "PERSON_FORMULAS", "label": "Fórmulas por pessoa", "owner": TENANT, "configKeys": ["pricing.formulas"]},
        {"code": "LOADINGS", "label": "Volatilidade e carregamentos", "owner": TENANT,
         "configKeys": ["pricing.actuarial_model"],
         "platformParameters": ["limits.max_acquisition_commission_pct"]},
        {"code": "ADJUSTMENTS", "label": "Agravamentos e descontos", "owner": TENANT,
         "configKeys": ["pricing.adjustments", "rules.custom"]},
        {"code": "LEGAL_TAXES", "label": "Impostos legais", "owner": PLATFORM, "configKeys": [],
         "platformParameters": ["tax.arseg_levy_pct", "tax.stamp_duty_pct"]},
        {"code": "CHARGES", "label": "Encargos comerciais", "owner": TENANT, "configKeys": ["pricing.taxes_fees"]},
        {"code": "QUOTE_FORMULAS", "label": "Fórmulas da cotação", "owner": TENANT, "configKeys": ["pricing.formulas"]},
        {"code": "PRODUCT_SETUP", "label": "Opções, campos e fórmulas do produto", "owner": TENANT,
         "configKeys": [setup_key], "productOnly": True},
        {"code": "MINIMUM_PREMIUM", "label": "Prémio mínimo", "owner": TENANT,
         "configKeys": ["product.minimum_premium"]},
        {"code": "FRACTIONATION", "label": "Fracionamento", "owner": TENANT,
         "configKeys": ["pricing.fractionation", "pricing.actuarial_model"]},
    ]


def _versions_of(key: str, product_id) -> list[str]:
    """A versão do produto (se a chave a admitir) e a geral."""
    return [product_key(key, product_id), key] if is_scopable(key) else [key]


def tariff_keys(product_id) -> list[str]:
    keys: list[str] = []
    for stage in _stages(product_id):
        for base in stage["configKeys"]:
            for key in _versions_of(base, product_id):
                if key not in keys:
                    keys.append(key)
    return keys


def _row(c: BusinessConfiguration | None) -> dict[str, Any] | None:
    if c is None:
        return None
    return {
        "configurationId": str(c.id), "versionNo": c.version_no, "status": c.status,
        "effectiveFrom": c.effective_from.isoformat() if c.effective_from else None,
        "effectiveTo": c.effective_to.isoformat() if c.effective_to else None,
        "createdBy": c.created_by, "rowVersion": c.row_version,
    }


def key_state(key: str, day: datetime.date) -> dict[str, Any]:
    rows = BusinessConfiguration.objects.filter(config_key=key)
    published = (
        rows.filter(status="PUBLISHED", effective_from__lte=day)
        .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=day))
        .order_by("-version_no").first()
    )
    draft = rows.filter(status__in=("DRAFT", "REJECTED")).order_by("-version_no").first()
    pending = rows.filter(status="PENDING_APPROVAL").order_by("-version_no").first()
    scheduled = rows.filter(status="PUBLISHED", effective_from__gt=day).order_by("effective_from").first()
    return {
        "configKey": key, "published": _row(published), "draft": _row(draft), "pending": _row(pending),
        "scheduled": _row(scheduled),
    }


def _summary(stage: str, values: dict[str, Any], product_id) -> dict[str, Any]:
    model = values.get("pricing.actuarial_model")
    formulas = values.get("pricing.formulas") or {}
    if stage == "PURE_PREMIUM":
        if model:
            return {"source": "ACTUARIAL_MODEL", "segments": sorted((model.get("assumptions") or {}).get("loadings") or {}),
                    "plans": sorted((model.get("plan_code_mapping") or {}))}
        premiums = (values.get("pricing.reference_premiums") or {}).get("premiums") or []
        return {"source": "REFERENCE_PREMIUMS" if premiums else None, "rows": len(premiums)}
    if stage == "RISK_FACTORS":
        regional = ((model or {}).get("adjustment_assumptions") or {}).get("regional_factors") or []
        return {"factors": len((values.get("pricing.factors") or {}).get("factors") or []),
                "actuarialRegionalFactors": len(regional)}
    if stage in ("PERSON_RULES", "ADJUSTMENTS"):
        from apps.business_config.domain.custom_rules import parse_rules

        try:
            rules = parse_rules((values.get("rules.custom") or {}).get("rules"))
        except InvalidConfiguration:
            rules = []
        scope = "PERSON" if stage == "PERSON_RULES" else "QUOTE"
        result = {"pricingRules": sum(1 for r in rules if r.is_pricing and r.scope == scope)}
        if stage == "ADJUSTMENTS":
            result["adjustments"] = len((values.get("pricing.adjustments") or {}).get("rules") or [])
        return result
    if stage in ("PERSON_FORMULAS", "QUOTE_FORMULAS"):
        phase = "PERSON" if stage == "PERSON_FORMULAS" else "QUOTE"
        return {"steps": sum(1 for r in formulas.get("rules") or []
                             if r.get("stage", "QUOTE") == phase and r.get("target", "TOTAL") == "TOTAL"
                             and r.get("active", True) is not False),
                "parameters": len(formulas.get("parameters") or [])}
    if stage == "LOADINGS":
        return {"loadings": (model or {}).get("assumptions", {}).get("loadings") if model else None}
    if stage == "LEGAL_TAXES":
        return {code: platform_parameter_service.describe(code)["value"]
                for code in ("tax.arseg_levy_pct", "tax.stamp_duty_pct")}
    if stage == "CHARGES":
        charges = (values.get("pricing.taxes_fees") or {}).get("charges") or []
        return {"charges": len(charges), "includedInPremium": sum(1 for c in charges if c.get("included_in_premium"))}
    if stage == "PRODUCT_SETUP":
        setup = values.get(product_setup_key(product_id)) or {}
        return {"optionGroups": len(setup.get("optionGroups") or []), "fields": len(setup.get("fields") or []),
                "formulas": len(setup.get("formulas") or [])}
    if stage == "MINIMUM_PREMIUM":
        return {"rows": len((values.get("product.minimum_premium") or {}).get("items") or [])}
    if stage == "FRACTIONATION":
        rows = (values.get("pricing.fractionation") or {}).get("installments")
        if rows is None and model:
            rows = (model.get("assumptions") or {}).get("payment_installments")
        return {"installments": rows or []}
    return {}


def _stage_scope(stage: dict[str, Any]) -> str:
    if stage.get("productOnly"):
        return "PRODUCT"
    return "PRODUCT_OR_TENANT" if any(is_scopable(k) for k in stage["configKeys"]) else "TENANT"


def describe_tariff(product) -> dict[str, Any]:
    day = timezone.localdate()
    states = {key: key_state(key, day) for key in tariff_keys(product.id)}
    # Valor em uso por chave geral: o do produto, se publicado, senão o geral.
    values: dict[str, Any] = {}
    in_use: dict[str, str] = {}
    for stage in _stages(product.id):
        for base in stage["configKeys"]:
            for key in _versions_of(base, product.id):
                if base not in values and states[key]["published"]:
                    values[base] = BusinessConfiguration.objects.get(id=states[key]["published"]["configurationId"]).value_json
                    in_use[base] = key
    stages = []
    for order, stage in enumerate(_stages(product.id), start=1):
        params = [platform_parameter_service.describe(code) for code in stage.get("platformParameters", [])]
        configurations = []
        for base in stage["configKeys"]:
            for key in _versions_of(base, product.id):
                scope = "PRODUCT" if stage.get("productOnly") or key != base else "TENANT"
                configurations.append({**states[key], "baseConfigKey": base, "scope": scope,
                                       "inUse": in_use.get(base) == key})
        stages.append({
            "order": order,
            "code": stage["code"],
            "label": stage["label"],
            "owner": stage["owner"],
            "editable": stage["owner"] == TENANT,
            "scope": _stage_scope(stage),
            "configurations": configurations,
            "platformParameters": [
                {"code": p["code"], "value": p["value"], "versionNo": p["versionNo"], "unit": p["unit"]} for p in params
            ],
            "summary": _summary(stage["code"], values, product.id),
        })
    open_drafts = [
        s["draft"] or s["pending"] for s in states.values() if s["draft"] or s["pending"]
    ]
    return {
        "productId": str(product.id),
        "productCode": product.code,
        "productName": product.name,
        "plans": [{"id": str(p.id), "code": p.code, "name": p.name, "status": p.status}
                  for p in product.plans.order_by("code")],
        "engine": {
            "owner": CODE,
            "order": [s["code"] for s in _stages(product.id)],
            "rounding": platform_parameter_service.platform_value("pricing.rounding_policy"),
            "structure": platform_parameter_service.platform_value("pricing.formula"),
        },
        "stages": stages,
        "openDrafts": open_drafts,
        "platformVersions": platform_parameter_service.snapshot(),
    }


# ----------------------------------------------------------------- simulação
class _Rollback(Exception):
    pass


def _owner(source_code: str | None, component_type: str | None = None) -> str:
    if source_code and source_code.startswith("PLATFORM_PARAMETER:"):
        return PLATFORM
    if component_type == "ROUNDING":
        return CODE
    return TENANT


def _apply_drafts(product, configuration_ids: list[str], include_open: bool, day: datetime.date) -> list[dict]:
    keys = tariff_keys(product.id)
    rows = BusinessConfiguration.objects.filter(config_key__in=keys, status__in=OPEN_STATUSES)
    if configuration_ids:
        chosen = list(rows.filter(id__in=configuration_ids))
        missing = set(map(str, configuration_ids)) - {str(c.id) for c in chosen}
        if missing:
            raise TariffSimulationError(
                f"Rascunhos inexistentes ou que não são da tarifa deste produto: {sorted(missing)}"
            )
    elif include_open:
        latest: dict[str, BusinessConfiguration] = {}
        for c in rows.order_by("config_key", "version_no"):
            latest[c.config_key] = c
        chosen = list(latest.values())
    else:
        chosen = []
    seen: set[str] = set()
    for c in chosen:
        if c.config_key in seen:
            raise TariffSimulationError(f"Escolha um só rascunho por configuração ('{c.config_key}')")
        seen.add(c.config_key)
        # Só dentro da transação revertida: o rascunho passa a valer hoje.
        BusinessConfiguration.objects.filter(id=c.id).update(
            status="PUBLISHED", effective_from=min(c.effective_from, day), effective_to=None,
        )
    return [_row(c) for c in chosen]


def _simulation_nif(proposer_type: str) -> str:
    """NIF fictício no formato AGT (a simulação é sempre revertida)."""
    digits = f"{secrets.randbelow(10**12):012d}"
    return digits[:10] if proposer_type == "ORGANISATION" else f"{digits[:9]}SM{digits[9:]}"


def _birth_date(age: int, day: datetime.date) -> datetime.date:
    try:
        return day.replace(year=day.year - age)
    except ValueError:  # 29 de fevereiro
        return day.replace(year=day.year - age, day=28)


def _installments(quote, run, frequency: str | None) -> dict[str, str]:
    from apps.policy.application.issuance_service import installment_amount

    frequencies = [frequency] if frequency else list(FREQUENCIES)
    return {f: str(installment_amount(quote, run.total_amount, f)) for f in frequencies}


def simulate_tariff(
    product, *, plan_id, members: list[dict[str, Any]], proposer_type: str = "INDIVIDUAL",
    selection: dict | None = None, actuarial_profile: dict | None = None, payment_frequency: str | None = None,
    configuration_ids: list[str] | None = None, include_open_drafts: bool = False,
) -> dict[str, Any]:
    from apps.client.infrastructure.models import InsuredMember, Proposer
    from apps.foundation.application.context import CurrentTenantProvider
    from apps.pricing.interfaces.serializers import PricingResponseSerializer
    from apps.quote.application import quote_service
    from apps.quote.infrastructure.models import Quote

    plan = product.plans.filter(id=plan_id).first()
    if plan is None:
        raise TariffSimulationError("O plano indicado não pertence a este produto")
    if not members or len(members) > MAX_SIMULATED_MEMBERS:
        raise TariffSimulationError(f"Indique entre 1 e {MAX_SIMULATED_MEMBERS} pessoas")
    if payment_frequency is not None and payment_frequency not in FREQUENCIES:
        raise TariffSimulationError(f"Frequência de pagamento inválida (use {list(FREQUENCIES)})")
    if proposer_type not in ("INDIVIDUAL", "ORGANISATION"):
        raise TariffSimulationError("Tipo de tomador inválido (INDIVIDUAL ou ORGANISATION)")

    tenant_id = CurrentTenantProvider.require().value
    day = timezone.localdate()
    result: dict[str, Any] = {}
    try:
        with transaction.atomic():
            applied = _apply_drafts(product, configuration_ids or [], include_open_drafts, day)
            attributes = {"actuarialProfile": actuarial_profile} if actuarial_profile else {}
            proposer = Proposer.objects.create(
                tenant_id=tenant_id, proposer_type=proposer_type, display_name="Simulação de tarifa",
                attributes_json=attributes, nif=_simulation_nif(proposer_type),
            )
            quote = quote_service.create_quote(proposer_id=proposer.id, plan_id=plan.id)
            for index, person in enumerate(members):
                age = person.get("age")
                if not isinstance(age, int) or not 0 <= age <= 120:
                    raise TariffSimulationError(f"members[{index}].age: idade entre 0 e 120")
                member = InsuredMember.objects.create(
                    tenant_id=tenant_id, proposer=proposer,
                    relationship_code=str(person.get("relationship") or ("TITULAR" if index == 0 else "FILHO")),
                    date_of_birth=_birth_date(age, quote.reference_date), sex_code=person.get("sex") or "M",
                    first_name=f"Pessoa {index + 1}",
                )
                quote = quote_service.add_quote_member(quote=quote, member_id=member.id, correlation_id=None)
            if selection:
                Quote.objects.filter(id=quote.id).update(selection_json=selection)
                quote.refresh_from_db()
            run = quote_service.price_quote(quote=quote, recalculate=True, correlation_id=None)
            quote.refresh_from_db()
            priced = PricingResponseSerializer(run).data
            components = []
            for component in priced.get("components") or []:
                components.append({**component, "owner": _owner(component.get("sourceCode"), component.get("type"))})
            result = {
                "productId": str(product.id),
                "planId": str(plan.id),
                "referenceDate": quote.reference_date.isoformat(),
                "currencyCode": priced.get("currencyCode"),
                "totalAmount": priced.get("totalAmount"),
                "installments": _installments(quote, run, payment_frequency),
                "components": components,
                "appliedDrafts": applied,
                "versions": priced.get("versions"),
                "steps": [
                    {"sequence": t.sequence_no, "stepCode": t.step_code, "ruleCode": t.rule_code,
                     "owner": CODE if t.step_code == "CONTEXT_RESOLVED" else TENANT,
                     "input": t.input_json, "output": t.output_json, "message": t.message}
                    for t in run.trace_steps.order_by("sequence_no")
                ],
                "persisted": False,
            }
            raise _Rollback
    except _Rollback:
        pass
    return result
