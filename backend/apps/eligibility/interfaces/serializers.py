"""DTOs matching ART-006 `EligibilityRequest`/`EligibilityResponse`
verbatim."""
from __future__ import annotations

from rest_framework import serializers


class EligibilityRequestSerializer(serializers.Serializer):
    """DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): `productVersionId`
    dropped — `planId` alone resolves the product via `Plan.productId`."""

    proposerId = serializers.UUIDField(allow_null=True, required=False, default=None)
    memberId = serializers.UUIDField(allow_null=True, required=False, default=None)
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


class EligibilityExecutionSerializer(serializers.Serializer):
    evaluationId = serializers.UUIDField(
        source="id"
    )

    decision = serializers.CharField()

    # Proponente
    proposerId = serializers.UUIDField(
        source="proposer_id",
        allow_null=True,
    )

    proposerName = serializers.SerializerMethodField()

    # Membro
    memberId = serializers.UUIDField(
        source="member_id",
        allow_null=True,
    )

    memberName = serializers.SerializerMethodField()

    # Plano
    planId = serializers.UUIDField(
        source="plan_id",
    )

    planName = serializers.CharField(
        source="plan.name",
    )

    # Produto
    productId = serializers.UUIDField(
        source="plan.product_id",
    )

    productName = serializers.CharField(
        source="plan.product.name",
    )

    ruleVersionId = serializers.UUIDField(
        source="rule_version_id",
        allow_null=True,
    )

    effectiveDate = serializers.SerializerMethodField()

    reasons = serializers.JSONField(
        source="evidence_json",
    )

    inputSnapshot = serializers.JSONField(
        source="input_snapshot_json",
    )

    evaluatedAt = serializers.DateTimeField(
        source="evaluated_at",
    )

    correlationId = serializers.CharField(
        source="correlation_id",
        allow_null=True,
    )

    def get_proposerName(self, obj):
        if not obj.proposer:
            return None

        return obj.proposer.display_name

    def get_memberName(self, obj):
        if not obj.member:
            return None

        return " ".join(
            part
            for part in (
                obj.member.first_name,
                obj.member.last_name,
            )
            if part
        ).strip() or None

    def get_effectiveDate(self, obj):
        snapshot = obj.input_snapshot_json or {}
        return snapshot.get("effectiveDate")