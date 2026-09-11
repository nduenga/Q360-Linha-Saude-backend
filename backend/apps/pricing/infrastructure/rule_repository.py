"""Resolves the applicable published `rule_domain=PRICING` RuleVersion for
a tenant and parses its JSON artifact into a `PricingRuleConfig` — same
pattern as `apps.eligibility.infrastructure.rule_repository` (Q360-S3-03).
"""
from __future__ import annotations

import datetime
import json

from django.db.models import Q

from apps.foundation.infrastructure.models import RuleVersion
from apps.pricing.domain.pricing_rules import PricingRuleConfig


def resolve_pricing_rule_version(*, code: str, effective_date: datetime.date) -> RuleVersion | None:
    return (
        RuleVersion.objects.filter(
            rule_set__rule_domain="PRICING",
            rule_set__code=code,
            status="PUBLISHED",
            effective_from__lte=effective_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )


def parse_pricing_config(rule_version: RuleVersion) -> PricingRuleConfig | None:
    if rule_version.artifact_type != "JSON" or not rule_version.artifact_ref:
        return None
    try:
        raw = json.loads(rule_version.artifact_ref)
    except (TypeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    return PricingRuleConfig.from_json(raw)
