"""DTOs matching ART-006 schemas verbatim (field names, nullability,
required sets). Do not add or rename a field without updating ART-006
first (DOC-004 s2 precedence rule) — these are `Serializer`, not
`ModelSerializer`, precisely so the wire shape never silently drifts from
the ORM model's own field names.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from apps.product.domain.enums import (
    PlanStatus,
    PricingParameterValueType,
    ProductStatus,
    VersionedConfigStatus,
)

# ART-005/ART-006 "decimal exacto serializado como string; nunca binary
# floating point" convention (DOC-004 s5 Money principle; demonstrated
# explicitly on ART-006's RatingFactor.factorValue). Applied here to
# PricingParameterValue.value when valueType=DECIMAL, since that field is
# `{}` (untyped) in ART-006 precisely because it is polymorphic on
# valueType and cannot carry its own `pattern` in the OpenAPI document.
_DECIMAL_STRING_PATTERN = r"^-?\d+(\.\d+)?$"


class ProductSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in ProductStatus])
    rowVersion = serializers.IntegerField(source="row_version")


class ProductCreateRequestSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=1, max_length=60)
    name = serializers.CharField(min_length=1, max_length=200)
    description = serializers.CharField(allow_null=True, required=False, default=None)


class ProductUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200)
    description = serializers.CharField(allow_null=True, required=False, default=None)
    rowVersion = serializers.IntegerField(source="row_version", min_value=0)
    # Pragmatic V1 addition, not in ART-006's ProductUpdateRequest - see
    # apps/product/application/product_service.update_product docstring.
    status = serializers.ChoiceField(choices=[s.value for s in ProductStatus], required=False, default=None)


class ProductVersionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    productId = serializers.UUIDField(source="product_id")
    versionNo = serializers.IntegerField(source="version_no", min_value=1)
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in VersionedConfigStatus])
    checksum = serializers.CharField(allow_null=True)


class ProductVersionCreateRequestSerializer(serializers.Serializer):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 3: a product/version is never
    given an expiry — `effectiveTo` is deliberately not a field here
    anymore (previously optional and always None in practice)."""

    effectiveFrom = serializers.DateField()


class PlanSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    productVersionId = serializers.UUIDField(source="product_version_id")
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in PlanStatus])
    rowVersion = serializers.IntegerField(source="row_version")


class PlanCreateRequestSerializer(serializers.Serializer):
    productVersionId = serializers.UUIDField()
    code = serializers.CharField(min_length=1, max_length=60)
    name = serializers.CharField(min_length=1, max_length=200)
    description = serializers.CharField(allow_null=True, required=False, default=None)
    # The 3 BASE (market-mandatory) coverages are always attached
    # automatically (product_service.create_plan) - never listed here.
    # Omit/empty this for a "basic" plan (BASE coverages only); each
    # COMPLEMENTARY id chosen must come from GET /api/v1/benefits.
    complementaryBenefitIds = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )


class PlanUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200)
    description = serializers.CharField(allow_null=True, required=False, default=None)
    rowVersion = serializers.IntegerField(source="row_version", min_value=0)


class VersionedConfigHeaderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    versionNo = serializers.IntegerField(source="version_no", min_value=1)
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in VersionedConfigStatus])
    checksum = serializers.CharField(allow_null=True)


class PricingParameterValueSerializer(serializers.Serializer):
    code = serializers.CharField()
    valueType = serializers.ChoiceField(choices=[t.value for t in PricingParameterValueType])
    value = serializers.JSONField()

    def validate(self, attrs: dict) -> dict:
        value_type = attrs["valueType"]
        value = attrs["value"]
        row: dict = {"parameter_code": attrs["code"], "value_type": value_type}

        if value_type == PricingParameterValueType.DECIMAL.value:
            if not isinstance(value, str) or not re.fullmatch(_DECIMAL_STRING_PATTERN, value):
                raise serializers.ValidationError(
                    {"value": "DECIMAL parameters must be a decimal serialised as a string (e.g. '12.50')."}
                )
            try:
                row["decimal_value"] = Decimal(value)
            except InvalidOperation as exc:
                raise serializers.ValidationError({"value": "Not a valid decimal."}) from exc
        elif value_type == PricingParameterValueType.INTEGER.value:
            if not isinstance(value, int) or isinstance(value, bool):
                raise serializers.ValidationError({"value": "INTEGER parameters must be a JSON integer."})
            row["integer_value"] = value
        elif value_type == PricingParameterValueType.BOOLEAN.value:
            if not isinstance(value, bool):
                raise serializers.ValidationError({"value": "BOOLEAN parameters must be a JSON boolean."})
            row["boolean_value"] = value
        elif value_type == PricingParameterValueType.TEXT.value:
            if not isinstance(value, str):
                raise serializers.ValidationError({"value": "TEXT parameters must be a JSON string."})
            row["text_value"] = value
        elif value_type == PricingParameterValueType.JSON.value:
            row["json_value"] = value

        attrs["_row"] = row
        return attrs


class PricingParameterSetRequestSerializer(serializers.Serializer):
    code = serializers.CharField()
    effectiveFrom = serializers.DateField()
    effectiveTo = serializers.DateField(allow_null=True, required=False, default=None)
    parameters = PricingParameterValueSerializer(many=True)

    def validate_parameters(self, parameters: list[dict]) -> list[dict]:
        if not parameters:
            raise serializers.ValidationError("At least one parameter is required.")
        codes = [p["code"] for p in parameters]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("Parameter codes must be unique within the set.")
        return parameters


class PricingParameterSetUpdateRequestSerializer(serializers.Serializer):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6 — only DRAFT is editable;
    `code`/`effectiveFrom`/`effectiveTo` are not editable fields."""

    parameters = PricingParameterValueSerializer(many=True)

    def validate_parameters(self, parameters: list[dict]) -> list[dict]:
        if not parameters:
            raise serializers.ValidationError("At least one parameter is required.")
        codes = [p["code"] for p in parameters]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("Parameter codes must be unique within the set.")
        return parameters


class BenefitSerializer(serializers.Serializer):
    """Pragmatic V1 addition, not in ART-006 — see
    apps/product/application/benefit_service.py module docstring and
    ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1."""

    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    category = serializers.CharField(source="benefit_type")
    description = serializers.CharField(allow_null=True)
    status = serializers.CharField()


class PlanBenefitSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    planId = serializers.UUIDField(source="plan_id")
    benefit = BenefitSerializer()
    configurationJson = serializers.JSONField(source="configuration_json")


class AddPlanBenefitRequestSerializer(serializers.Serializer):
    benefitId = serializers.UUIDField()
