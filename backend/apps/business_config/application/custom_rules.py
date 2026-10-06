"""Regras "Quando… então…" publicadas (`rules.custom`) prontas para os motores."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Mapping

from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.domain.custom_rules import CONFIG_KEY, CustomRule, parse_rules
from apps.business_config.domain.shape import flatten


@dataclass(frozen=True)
class PublishedRules:
    rules: tuple[CustomRule, ...] = ()
    version: dict[str, Any] | None = None

    def pricing(self, scope: str) -> list[CustomRule]:
        return [r for r in self.rules if r.is_pricing and r.scope == scope]

    def underwriting(self, scope: str) -> list[CustomRule]:
        return [r for r in self.rules if not r.is_pricing and r.scope == scope]


def load_published_rules(effective_date: datetime.date) -> PublishedRules:
    config = BusinessConfigurationResolver.get(CONFIG_KEY, effective_date=effective_date)
    if config is None:
        return PublishedRules()
    rows = flatten(CONFIG_KEY, config.value_json).get("rules")
    return PublishedRules(
        rules=tuple(parse_rules(rows)),
        version={
            "configurationId": str(config.id),
            "configKey": config.config_key,
            "versionNo": config.version_no,
            "checksum": config.checksum,
        },
    )


def person_facts(
    *,
    age: int | None,
    members_count: int,
    plan_code: str | None,
    plan_name: str | None,
    dimensions: Mapping[str, Any],
    relationship: str | None,
    product: tuple[str | None, str | None] = (),
) -> dict[str, Any]:
    """Valores com que as condições de uma pessoa são avaliadas."""
    facts = quote_facts(
        members_count=members_count, plan_code=plan_code, plan_name=plan_name, dimensions=dimensions, product=product
    )
    facts["age"] = age
    facts["relationship"] = relationship
    return facts


def quote_facts(
    *,
    members_count: int,
    plan_code: str | None,
    plan_name: str | None,
    dimensions: Mapping[str, Any],
    product: tuple[str | None, str | None] = (),
) -> dict[str, Any]:
    return {
        "members_count": members_count,
        "product": product,  # (código, nome) do produto a que o plano pertence
        "plan": (plan_code, plan_name),  # o GTE pode escrever o código ou o nome
        "segment": dimensions.get("segment"),
        "participation_option": dimensions.get("participationOption"),
    }

