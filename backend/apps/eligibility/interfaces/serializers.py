"""DTOs matching ART-006 `EligibilityRequest`/`EligibilityResponse`
verbatim."""
from __future__ import annotations

from rest_framework import serializers


class EligibilityRequestSerializer(serializers.Serializer):
    proposerId = serializers.UUIDField(allow_null=True, required=False, default=None)
    memberId = serializers.UUIDField(allow_null=True, required=False, default=None)
    productVersionId = serializers.UUIDField()
    planId = serializers.UUIDField()
    effectiveDate = serializers.DateField()
    context = serializers.JSONField()


class EligibilityMessageSerializer(serializers.Serializer):
    code = serializers.CharField()
    severity = serializers.ChoiceField(choices=["INFO", "WARNING", "ERROR"])
    message = serializers.CharField()


class EligibilityResponseSerializer(serializers.Serializer):
    evaluationId = serializers.UUIDField(source="id")
    decision = serializers.CharField()
    ruleVersionId = serializers.UUIDField(source="rule_version_id", allow_null=True)
    messages = serializers.SerializerMethodField()
    evaluatedAt = serializers.DateTimeField(source="evaluated_at")

    def get_messages(self, obj) -> list[dict]:
        return obj.evidence_json
