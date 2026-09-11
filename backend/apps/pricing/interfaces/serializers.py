"""DTOs matching ART-006 `RatingFactor`/`RatingTableRequest` verbatim.
`factorValue` follows the same "decimal exacto serializado como string"
rule ART-006 states explicitly on this exact field (unlike
PricingParameterValue, this one has its own `pattern` in the schema)."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

_DECIMAL_STRING_PATTERN = r"^-?\d+(\.\d+)?$"


class RatingFactorSerializer(serializers.Serializer):
    factorCode = serializers.CharField()
    dimensions = serializers.JSONField()
    # JSONField, not CharField: CharField's to_internal_value() silently
    # coerces a JSON number to a string (`str(1.5)` -> `"1.5"`) before
    # validate_factorValue() ever runs, defeating the "must arrive as a
    # string" check. JSONField preserves the original JSON type so the
    # isinstance check below is meaningful (same fix already applied to
    # apps.product.interfaces.serializers.PricingParameterValueSerializer).
    factorValue = serializers.JSONField()
    priority = serializers.IntegerField(required=False, default=0)

    def validate_dimensions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("dimensions must be a JSON object.")
        return value

    def validate_factorValue(self, value) -> Decimal:
        if not isinstance(value, str) or not re.fullmatch(_DECIMAL_STRING_PATTERN, value):
            raise serializers.ValidationError(
                "factorValue must be a decimal serialised as a string (e.g. '1.05')."
            )
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise serializers.ValidationError("Not a valid decimal.") from exc


class RatingTableRequestSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    effectiveFrom = serializers.DateField()
    effectiveTo = serializers.DateField(allow_null=True, required=False, default=None)
    currencyCode = serializers.RegexField(r"^[A-Z]{3}$", allow_null=True, required=False, default=None)
    factors = RatingFactorSerializer(many=True)

    def validate_factors(self, factors: list[dict]) -> list[dict]:
        if not factors:
            raise serializers.ValidationError("At least one factor is required.")
        return factors


class VersionedConfigHeaderSerializer(serializers.Serializer):
    """Re-declared here rather than imported from `apps.product`: `pricing`
    and `product` are sibling modules (see domain/enums.py note)."""

    id = serializers.UUIDField()
    code = serializers.CharField()
    versionNo = serializers.IntegerField(source="version_no", min_value=1)
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True)
    status = serializers.CharField()
    checksum = serializers.CharField(allow_null=True)
