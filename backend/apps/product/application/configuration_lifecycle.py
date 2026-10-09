"""Autonomia do GTE sobre parâmetros técnicos e tarifários (R7): histórico,
diferenças entre versões e **reverter** (rollback) de tabelas de tarifação
(`rating-table`), conjuntos de parâmetros (`pricing-parameter-set`) e regras
(`rule-version`).

Versões já publicadas nunca se alteram nem se apagam (há cotações e cálculos
que as referenciam). Reverter para a versão N é, por isso, **criar uma nova
versão** com o conteúdo da N, publicá-la e retirar as versões publicadas
mais recentes que estão a ser revertidas — tudo numa transação, com motivo
obrigatório e auditoria `before`/`after`. O histórico fica intacto.

A nova versão nasce com `effective_from` igual ao mais recente entre as
versões publicadas do código (e a da versão restaurada): a resolução por
data escolhe a maior `effective_from` e depois a maior `version_no`, por isso
uma data anterior deixaria a versão revertida a perder para a defeituosa.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from django.db import transaction
from rest_framework.exceptions import NotFound

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.rule_service import (
    create_rule_version,
    publish_rule_version,
    retire_rule_version,
)
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.foundation.infrastructure.models import RuleVersion
from apps.pricing.application.rating_table_service import create_rating_table, publish_rating_table, retire_rating_table
from apps.pricing.infrastructure.models import RatingTable
from apps.product.application.configuration import _header
from apps.product.application.pricing_parameter_service import (
    create_pricing_parameter_set,
    publish_pricing_parameter_set,
    retire_pricing_parameter_set,
)
from apps.product.infrastructure.models import PricingParameter, PricingParameterSet

_audit = AuditService(DjangoAuditRepositoryAdapter())
CONFIG_TYPES = ("pricing-parameter-set", "rating-table", "rule-version")


class ConfigurationRollbackError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


def load(config_type: str, config_id: uuid.UUID):
    if config_type == "pricing-parameter-set":
        obj = PricingParameterSet.objects.filter(id=config_id).first()
    elif config_type == "rating-table":
        obj = RatingTable.objects.filter(id=config_id).first()
    elif config_type == "rule-version":
        obj = RuleVersion.objects.select_related("rule_set").filter(id=config_id).first()
    else:
        raise NotFound(f"O tipo de configuração '{config_type}' não está disponível")
    if obj is None:
        raise NotFound(f"{config_type} {config_id} não foi encontrado")
    return obj


def code_of(config_type: str, obj) -> str:
    return obj.rule_set.code if config_type == "rule-version" else obj.code


def header(config_type: str, obj) -> dict[str, Any]:
    return _header(
        id=obj.id,
        code=code_of(config_type, obj),
        version_no=obj.version_no,
        effective_from=obj.effective_from,
        effective_to=obj.effective_to,
        status=obj.status,
        checksum=obj.artifact_checksum if config_type == "rule-version" else obj.checksum,
    )


def _versions_of(config_type: str, obj) -> list:
    if config_type == "pricing-parameter-set":
        return list(PricingParameterSet.objects.filter(code=obj.code).order_by("-version_no"))
    if config_type == "rating-table":
        return list(RatingTable.objects.filter(code=obj.code).order_by("-version_no"))
    return list(RuleVersion.objects.select_related("rule_set").filter(rule_set=obj.rule_set).order_by("-version_no"))


def history(*, config_type: str, config_id: uuid.UUID) -> list[dict[str, Any]]:
    obj = load(config_type, config_id)
    out = []
    for version in _versions_of(config_type, obj):
        item = header(config_type, version)
        item["publishedAt"] = version.published_at.isoformat() if version.published_at else None
        item["publishedBy"] = version.published_by
        item["createdAt"] = version.created_at.isoformat() if hasattr(version, "created_at") and version.created_at else None
        out.append(item)
    return out


# --------------------------------------------------------------------- content
def _content(config_type: str, obj) -> dict[str, Any]:
    """Comparable content of a version, keyed by a stable identity."""
    if config_type == "rating-table":
        rows = {}
        for factor in obj.factors.all():
            key = f"{factor.factor_code}|{json.dumps(factor.dimension_json, sort_keys=True)}|p{factor.priority}"
            rows[key] = {"factorValue": format(factor.factor_value.normalize(), "f"), "factorCode": factor.factor_code,
                         "dimensions": factor.dimension_json, "priority": factor.priority}
        return {"currencyCode": obj.currency_code, "items": rows}
    if config_type == "pricing-parameter-set":
        rows = {}
        for parameter in PricingParameter.objects.filter(parameter_set=obj):
            value = {
                "DECIMAL": parameter.decimal_value,
                "INTEGER": parameter.integer_value,
                "BOOLEAN": parameter.boolean_value,
                "TEXT": parameter.text_value,
                "JSON": parameter.json_value,
            }[parameter.value_type]
            rows[parameter.parameter_code] = {"valueType": parameter.value_type, "value": format(value.normalize(), "f") if hasattr(value, "normalize") else value}
        return {"currencyCode": None, "items": rows}
    artifact: Any = obj.artifact_ref
    if obj.artifact_type == "JSON" and obj.artifact_ref:
        try:
            artifact = json.loads(obj.artifact_ref)
        except json.JSONDecodeError:
            artifact = obj.artifact_ref
    return {"currencyCode": None, "items": _flatten(artifact), "artifactType": obj.artifact_type}


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value):
            out.update(_flatten(value[key], f"{prefix}.{key}" if prefix else key))
        return out
    if isinstance(value, list):
        out = {}
        for index, item in enumerate(value):
            out.update(_flatten(item, f"{prefix}[{index}]"))
        if not value:
            out[prefix] = []
        return out
    return {prefix or "$": value}


def diff(*, config_type: str, config_id: uuid.UUID, against_id: uuid.UUID) -> dict[str, Any]:
    first = load(config_type, config_id)
    second = load(config_type, against_id)
    if code_of(config_type, first) != code_of(config_type, second):
        raise ConfigurationRollbackError("Só é possível comparar versões do mesmo código")
    a, b = _content(config_type, first), _content(config_type, second)
    changes: list[dict[str, Any]] = []
    if a["currencyCode"] != b["currencyCode"]:
        changes.append({"kind": "CHANGED", "key": "currencyCode", "before": a["currencyCode"], "after": b["currencyCode"]})
    for key in sorted(set(a["items"]) | set(b["items"])):
        before, after = a["items"].get(key), b["items"].get(key)
        if before is None:
            changes.append({"kind": "ADDED", "key": key, "before": None, "after": after})
        elif after is None:
            changes.append({"kind": "REMOVED", "key": key, "before": before, "after": None})
        elif before != after:
            changes.append({"kind": "CHANGED", "key": key, "before": before, "after": after})
    return {"from": header(config_type, first), "to": header(config_type, second), "changes": changes}


# -------------------------------------------------------------------- rollback
def _copy_as_new_version(config_type: str, target, effective_from):
    if config_type == "rating-table":
        rows = [
            {"factorCode": f.factor_code, "dimensions": f.dimension_json, "factorValue": f.factor_value, "priority": f.priority}
            for f in target.factors.all()
        ]
        return create_rating_table(
            code=target.code, name=target.name, effective_from=effective_from, effective_to=None,
            currency_code=target.currency_code, factor_rows=rows,
        )
    if config_type == "pricing-parameter-set":
        rows = [
            {
                "parameter_code": p.parameter_code,
                "value_type": p.value_type,
                "decimal_value": p.decimal_value,
                "integer_value": p.integer_value,
                "boolean_value": p.boolean_value,
                "text_value": p.text_value,
                "json_value": p.json_value,
            }
            for p in PricingParameter.objects.filter(parameter_set=target)
        ]
        return create_pricing_parameter_set(code=target.code, effective_from=effective_from, effective_to=None, parameter_rows=rows)
    return create_rule_version(
        code=target.rule_set.code, name=target.rule_set.name, rule_domain=target.rule_set.rule_domain,
        effective_from=effective_from, effective_to=None, artifact_type=target.artifact_type,
        artifact_ref=target.artifact_ref, artifact_checksum=target.artifact_checksum,
    )


def rollback(*, config_type: str, config_id: uuid.UUID, reason: str | None) -> dict[str, Any]:
    reason = require_reason(reason)
    target = load(config_type, config_id)
    if target.status == "DRAFT":
        raise ConfigurationRollbackError("Um rascunho (DRAFT) nunca esteve em vigor: publique-o em vez de o restaurar")
    versions = _versions_of(config_type, target)
    newer_published = [v for v in versions if v.status == "PUBLISHED" and v.version_no > target.version_no]
    if target.status == "PUBLISHED" and not newer_published:
        raise ConfigurationRollbackError(f"A versão {target.version_no} já é a versão publicada atual")
    published = [v for v in versions if v.status == "PUBLISHED"]
    effective_from = max([v.effective_from for v in published] + [target.effective_from])

    with transaction.atomic():
        retired_headers = []
        for version in newer_published:
            if config_type == "rating-table":
                retire_rating_table(version)
            elif config_type == "pricing-parameter-set":
                retire_pricing_parameter_set(version)
            else:
                retire_rule_version(version)
            version.refresh_from_db()
            retired_headers.append(header(config_type, version))
        if target.status == "PUBLISHED":
            # The restored version itself is still in force (an older, valid
            # one): nothing to copy — retiring the newer ones is the rollback.
            restored = target
        else:
            created = _copy_as_new_version(config_type, target, effective_from)
            if config_type == "rating-table":
                restored = publish_rating_table(created)
            elif config_type == "pricing-parameter-set":
                restored = publish_pricing_parameter_set(created)
            else:
                restored = publish_rule_version(created)
    result = {
        "restoredFrom": header(config_type, target),
        "current": header(config_type, restored),
        "retired": retired_headers,
    }
    _audit.record(
        action="configuration.rolled_back",
        entity_type={"rating-table": "RatingTable", "pricing-parameter-set": "PricingParameterSet", "rule-version": "RuleVersion"}[config_type],
        entity_id=str(restored.id),
        metadata=change_metadata(
            before={"retired": retired_headers},
            after={"current": result["current"]},
            reason=reason,
            configType=config_type,
            restoredFromVersionNo=target.version_no,
        ),
    )
    return result
