"""Dispatcher for POST /api/v1/configuration/{configType}/{configId}/publish
(ART-006: one shared endpoint across pricing-parameter-set, rating-table,
rule-version).

Returns a plain dict already shaped as ART-006's `VersionedConfigHeader`
(camelCase) rather than a model instance: the three config types are
different models from different apps (`PricingParameterSet` here,
`RuleVersion` in `apps.foundation` — `product` may depend on `foundation`,
so this is the one direction that's architecturally fine) with different
"code" access paths (`obj.code` vs `obj.rule_set.code`); normalising to one
dict here avoids the view needing type-specific serializer selection.

`rating-table` (S4) does not exist yet, so publishing against it correctly
reads as "not found" — the record genuinely cannot exist yet.
"""
from __future__ import annotations

import uuid

from rest_framework.exceptions import NotFound

from apps.foundation.application.rule_service import publish_rule_version
from apps.foundation.infrastructure.models import RuleVersion
from apps.product.application.pricing_parameter_service import publish_pricing_parameter_set
from apps.product.infrastructure.models import PricingParameterSet


def _header(*, id, code: str, version_no: int, effective_from, effective_to, status: str, checksum: str | None) -> dict:
    return {
        "id": str(id),
        "code": code,
        "versionNo": version_no,
        "effectiveFrom": effective_from.isoformat(),
        "effectiveTo": effective_to.isoformat() if effective_to else None,
        "status": status,
        "checksum": checksum,
    }


def publish_configuration(*, config_type: str, config_id: uuid.UUID) -> dict:
    if config_type == "pricing-parameter-set":
        try:
            parameter_set = PricingParameterSet.objects.get(id=config_id)
        except PricingParameterSet.DoesNotExist as exc:
            raise NotFound(f"PricingParameterSet {config_id} not found") from exc
        published = publish_pricing_parameter_set(parameter_set)
        return _header(
            id=published.id,
            code=published.code,
            version_no=published.version_no,
            effective_from=published.effective_from,
            effective_to=published.effective_to,
            status=published.status,
            checksum=published.checksum,
        )

    if config_type == "rule-version":
        try:
            rule_version = RuleVersion.objects.select_related("rule_set").get(id=config_id)
        except RuleVersion.DoesNotExist as exc:
            raise NotFound(f"RuleVersion {config_id} not found") from exc
        published = publish_rule_version(rule_version)
        return _header(
            id=published.id,
            code=published.rule_set.code,
            version_no=published.version_no,
            effective_from=published.effective_from,
            effective_to=published.effective_to,
            status=published.status,
            checksum=published.artifact_checksum,
        )

    raise NotFound(f"Configuration type '{config_type}' is not available yet")
