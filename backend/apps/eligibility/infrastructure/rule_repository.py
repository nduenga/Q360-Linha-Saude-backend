"""Concrete adapter for DOC-004 s9 `EligibilityRulePort`: resolves the
applicable published `rule_domain=ELIGIBILITY` RuleVersion for a tenant and
parses its JSON artifact into an `EligibilityRuleConfig`.
"""
from __future__ import annotations

import datetime
import json

from django.db.models import Q

from apps.eligibility.domain.evaluation import EligibilityRuleConfig
from apps.foundation.infrastructure.models import RuleVersion


def resolve_eligibility_rule_version(effective_date: datetime.date) -> RuleVersion | None:
    return (
        RuleVersion.objects.filter(
            rule_set__rule_domain="ELIGIBILITY",
            status="PUBLISHED",
            effective_from__lte=effective_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .order_by("-effective_from", "-version_no")
        .first()
    )


def parse_config(rule_version: RuleVersion) -> EligibilityRuleConfig | None:
    if rule_version.artifact_type != "JSON" or not rule_version.artifact_ref:
        return None
    try:
        raw = json.loads(rule_version.artifact_ref)
    except (TypeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    return EligibilityRuleConfig.from_json(raw)
