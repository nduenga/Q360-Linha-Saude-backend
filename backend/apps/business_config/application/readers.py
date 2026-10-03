"""Leitura das configurações de negócio PUBLISHED por parte dos motores.

Regra única: o que a empresa publica na interface (`BusinessConfiguration`)
sobrepõe-se ao que está nas definições do plano; sem configuração publicada
nada muda (os valores do plano continuam a valer). Nenhum valor comercial
nasce aqui.

`BusinessSnapshot.load(on)` faz uma única consulta com todas as chaves
vigentes do inquilino na data `on`.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from django.db import models
from django.utils import timezone

from apps.business_config.domain.shape import flatten
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.application.context import CurrentTenantProvider


def _fold(value: Any) -> str:
    return str(value or "").strip().casefold()


@dataclass(frozen=True)
class BusinessSnapshot:
    values: dict[str, dict[str, Any]] = field(default_factory=dict)
    versions: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, on: datetime.date | None = None) -> "BusinessSnapshot":
        day = on or timezone.localdate()
        tenant = CurrentTenantProvider.require().value
        rows = (
            BusinessConfiguration.objects.filter(tenant_id=tenant, status="PUBLISHED", effective_from__lte=day)
            .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=day))
            .order_by("config_key", "-effective_from", "-version_no")
        )
        values: dict[str, dict[str, Any]] = {}
        versions: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.config_key in values:
                continue
            values[row.config_key] = flatten(row.config_key, row.value_json)
            versions[row.config_key] = {"configurationId": str(row.id), "versionNo": row.version_no, "checksum": row.checksum}
        return cls(values=values, versions=versions)

    def get(self, key: str) -> dict[str, Any] | None:
        return self.values.get(key)

    def rows(self, key: str, list_name: str) -> list[dict[str, Any]]:
        raw = (self.values.get(key) or {}).get(list_name)
        return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def matches_plan(row_plan: Any, plan, settings: dict[str, Any] | None = None) -> bool:
    """Uma linha sem plano aplica-se a todos; senão casa por código, nome ou escalão."""
    wanted = _fold(row_plan)
    if not wanted:
        return True
    candidates = {_fold(plan.code), _fold(plan.name), _fold((settings or plan.settings_json or {}).get("tier"))}
    return wanted in candidates


def matches_coverage(row_coverage: Any, code: str, name: str) -> bool:
    wanted = _fold(row_coverage)
    return bool(wanted) and wanted in {_fold(code), _fold(name)}


def number(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def integer(raw: Any) -> int | None:
    value = number(raw)
    return int(value) if value is not None else None
