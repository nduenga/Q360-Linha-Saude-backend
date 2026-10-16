"""Converte a tarifa antiga (`RatingTable` + `PricingParameterSet`) para a
configuração de negócio (`pricing.reference_premiums` e `pricing.factors`).

Cria RASCUNHOS, nunca publica: alguém revê, simula (`/products/{id}/tariff/
simulate`) e submete; outra pessoa aprova. Só converte o que dá exatamente o
mesmo prémio; o resto vem no relatório como não convertido, com o motivo.

Diferenças entre os dois formatos que a conversão respeita:
  - Antigo: um prémio-base único (`BASE_PREMIUM`) para todos os planos e
    idades → novo: uma linha por plano, de 0 anos sem limite.
  - Antigo: por código de fator aplica-se só a linha de maior prioridade
    cujas dimensões coincidem → novo: aplicam-se todas as linhas que
    coincidem, uma dimensão por linha. Converte-se um código de fator quando
    cada linha tem no máximo uma dimensão e não mistura a linha geral (sem
    dimensões) com linhas específicas."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.business_config.application.service import create_configuration
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.pricing.infrastructure.models import RatingTable
from apps.product.infrastructure.models import Plan, PricingParameterSet

BASE_PREMIUM = "BASE_PREMIUM"
# A linha geral (sem dimensões) passa a «qualquer plano»: o código do plano
# está sempre no contexto do cálculo.
ANY_DIMENSION = "planCode"


def _in_effect(qs, day: datetime.date):
    return (
        qs.filter(status="PUBLISHED", effective_from__lte=day)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
        .order_by("code", "-version_no")
    )


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _convert_factors(table: RatingTable) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_code: dict[str, list] = {}
    for factor in table.factors.order_by("factor_code", "-priority"):
        by_code.setdefault(factor.factor_code, []).append(factor)
    converted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for code, rows in sorted(by_code.items()):
        dims = [r.dimension_json or {} for r in rows]
        if any(len(d) > 1 for d in dims):
            skipped.append({"factorCode": code, "reason": "Linhas com mais de uma dimensão (o formato novo usa uma)."})
            continue
        general = [r for r, d in zip(rows, dims) if not d]
        specific = [(r, d) for r, d in zip(rows, dims) if d]
        if general and specific:
            skipped.append({"factorCode": code,
                            "reason": "Mistura a linha geral com linhas específicas (no formato novo aplicar-se-iam as duas)."})
            continue
        if len(general) > 1:
            skipped.append({"factorCode": code, "reason": "Mais do que uma linha geral para o mesmo fator."})
            continue
        seen: set[tuple[str, str]] = set()
        clash = False
        for row, dim in specific:
            ((dimension, value),) = dim.items()
            key = (dimension, str(value))
            if key in seen:
                clash = True
                break
            seen.add(key)
        if clash:
            skipped.append({"factorCode": code, "reason": "Duas linhas para a mesma dimensão e valor (prioridades)."})
            continue
        if general:
            converted.append({"code": code, "dimension": ANY_DIMENSION, "condition": "*",
                              "factor": _decimal_text(general[0].factor_value)})
        for row, dim in specific:
            ((dimension, value),) = dim.items()
            converted.append({"code": code, "dimension": dimension, "condition": str(value),
                              "factor": _decimal_text(row.factor_value)})
    return converted, skipped


def migrate(request=None, *, dry_run: bool = False, effective_from: datetime.date | None = None) -> dict[str, Any]:
    day = timezone.localdate()
    start = effective_from or day
    report: dict[str, Any] = {"dryRun": dry_run, "effectiveFrom": start.isoformat(), "created": [], "skipped": [],
                              "warnings": []}

    if BusinessConfiguration.objects.filter(config_key="pricing.reference_premiums", status="PUBLISHED").exists():
        report["warnings"].append("Já existe pricing.reference_premiums publicada: a tarifa antiga já não é usada.")

    parameter_sets = list(_in_effect(PricingParameterSet.objects.all(), day))
    tables = list(_in_effect(RatingTable.objects.all(), day))
    if len({p.code for p in parameter_sets}) > 1 or len({t.code for t in tables}) > 1:
        report["warnings"].append("Há mais do que uma tabela ou conjunto de parâmetros em vigor: converte-se o primeiro "
                                  "de cada (o motor também recusa esta situação).")
    parameter_set = parameter_sets[0] if parameter_sets else None
    table = tables[0] if tables else None
    report["source"] = {
        "parameterSet": {"code": parameter_set.code, "versionNo": parameter_set.version_no} if parameter_set else None,
        "ratingTable": {"code": table.code, "versionNo": table.version_no} if table else None,
    }

    premiums_value = None
    if parameter_set is not None:
        base = parameter_set.parameters.filter(parameter_code=BASE_PREMIUM).first()
        if base is None or base.decimal_value is None:
            report["skipped"].append({"item": "pricing.reference_premiums",
                                      "reason": f"O conjunto '{parameter_set.code}' não tem BASE_PREMIUM decimal."})
        else:
            plans = list(Plan.objects.order_by("code").values_list("code", flat=True).distinct())
            premiums_value = {
                "currency_code": (table.currency_code if table and table.currency_code else "AOA"),
                "premiums": [{"plan": code, "age_from": 0, "age_to": None,
                              "annual_premium": _decimal_text(base.decimal_value)} for code in plans],
            }
            if not plans:
                premiums_value = None
                report["skipped"].append({"item": "pricing.reference_premiums", "reason": "O tenant não tem planos."})
    else:
        report["skipped"].append({"item": "pricing.reference_premiums", "reason": "Sem conjunto de parâmetros em vigor."})

    factors_value = None
    if table is not None:
        converted, skipped = _convert_factors(table)
        report["skipped"].extend({"item": "pricing.factors", **s} for s in skipped)
        factors_value = {"factors": converted}
    else:
        report["skipped"].append({"item": "pricing.factors", "reason": "Sem tabela de tarifação em vigor."})

    metadata = {"migratedFrom": report["source"], "migratedAt": timezone.now().isoformat()}
    for key, value in (("pricing.reference_premiums", premiums_value), ("pricing.factors", factors_value)):
        if value is None:
            continue
        if dry_run:
            report["created"].append({"configKey": key, "value": value, "status": "DRY_RUN"})
            continue
        created = create_configuration(request, key, value, start, None, metadata)
        report["created"].append({"configKey": key, "configurationId": str(created.id),
                                  "versionNo": created.version_no, "status": created.status, "value": value})
    return report
