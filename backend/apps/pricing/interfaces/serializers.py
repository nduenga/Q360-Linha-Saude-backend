"""DTOs matching ART-006 `RatingFactor`/`RatingTableRequest` verbatim.
`factorValue` follows the same "decimal exacto serializado como string"
rule ART-006 states explicitly on this exact field (unlike
PricingParameterValue, this one has its own `pattern` in the schema)."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from apps.pricing.domain.money import round_amount

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


class RatingTableUpdateRequestSerializer(serializers.Serializer):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6 — only DRAFT is editable;
    `code`/`effectiveFrom`/`effectiveTo` are not editable fields (identity
    and vigência of a version, not content)."""

    name = serializers.CharField()
    currencyCode = serializers.RegexField(r"^[A-Z]{3}$", allow_null=True, required=False, default=None)
    factors = RatingFactorSerializer(many=True)

    def validate_factors(self, factors: list[dict]) -> list[dict]:
        if not factors:
            raise serializers.ValidationError("At least one factor is required.")
        return factors


class PricingCalculateRequestSerializer(serializers.Serializer):
    productVersionId = serializers.UUIDField()
    planId = serializers.UUIDField()
    effectiveDate = serializers.DateField()
    memberIds = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    context = serializers.JSONField(required=False, default=dict)


class PricingScenarioRequestSerializer(serializers.Serializer):
    basePricingRunId = serializers.UUIDField()
    name = serializers.CharField(min_length=1, max_length=200)
    overrides = serializers.JSONField()


def _money_str(value) -> str | None:
    """`PricingComponent.base_amount`/`adjustment_amount`/`result_amount`
    and `PricingRun.total_amount` are stored as `numeric(30,8)` (ART-012
    V015/V016) — reading them back gives a Decimal padded to 8 decimal
    places (e.g. `100.00000000`), not the 2dp the rounding policy actually
    computed. Re-round at the serialization boundary so the API always
    shows the policy's real precision (`apps.pricing.domain.money.round_amount`)."""
    if value is None:
        return None
    return str(round_amount(value))


class PricingComponentSerializer(serializers.Serializer):
    order = serializers.IntegerField(source="component_order")
    code = serializers.CharField(source="component_code")
    type = serializers.CharField(source="component_type")
    baseAmount = serializers.SerializerMethodField()
    factorValue = serializers.CharField(source="factor_value", allow_null=True)
    adjustmentAmount = serializers.SerializerMethodField()
    resultAmount = serializers.SerializerMethodField()
    sourceCode = serializers.CharField(source="source_code", allow_null=True)
    sourceVersion = serializers.CharField(source="source_version", allow_null=True)

    def get_baseAmount(self, obj) -> str | None:
        return _money_str(obj.base_amount)

    def get_adjustmentAmount(self, obj) -> str | None:
        return _money_str(obj.adjustment_amount)

    def get_resultAmount(self, obj) -> str:
        return _money_str(obj.result_amount)


class PricingResponseSerializer(serializers.Serializer):
    """DTO matching ART-006 `PricingResponse` verbatim. `status` is
    hardcoded to `CALCULATED`: the schema's own enum only allows that one
    value here — a FAILED run never reaches this serializer, it surfaces
    as a `PRICING-FAILED` ProblemDetail instead (see interfaces/views.py)."""

    pricingRunId = serializers.UUIDField(source="id")
    status = serializers.SerializerMethodField()
    currencyCode = serializers.CharField(source="currency_code")
    totalAmount = serializers.SerializerMethodField()
    components = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()
    calculatedAt = serializers.DateTimeField(source="completed_at")

    def get_status(self, obj) -> str:
        return "CALCULATED"

    def get_totalAmount(self, obj) -> str:
        return _money_str(obj.total_amount)

    def get_components(self, obj) -> list[dict]:
        return PricingComponentSerializer(obj.components.order_by("component_order"), many=True).data

    def get_versions(self, obj) -> dict:
        return {
            "productVersionId": obj.product_version_id,
            "ratingTableId": obj.rating_table_id,
            "parameterSetId": obj.parameter_set_id,
            "ruleVersionId": obj.rule_version_id,
            "roundingPolicyCode": obj.rounding_policy_code,
            "roundingPolicyVersion": obj.rounding_policy_version,
        }


class PricingTraceStepSerializer(serializers.Serializer):
    sequence = serializers.IntegerField(source="sequence_no")
    stepCode = serializers.CharField(source="step_code")
    ruleCode = serializers.CharField(source="rule_code", allow_null=True)
    message = serializers.CharField(allow_null=True)
    input = serializers.JSONField(source="input_json", allow_null=True)
    output = serializers.JSONField(source="output_json", allow_null=True)


class PricingExplanationSerializer(serializers.Serializer):
    pricingRunId = serializers.UUIDField(source="id")
    steps = serializers.SerializerMethodField()

    def get_steps(self, obj) -> list[dict]:
        return PricingTraceStepSerializer(obj.trace_steps.order_by("sequence_no"), many=True).data


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
