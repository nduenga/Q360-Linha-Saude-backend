"""DTOs matching ART-006 `RuleSetVersionRequest`/`VersionedConfigHeader`
verbatim (see apps/product/interfaces/serializers.py for the general
"why plain Serializer" rationale). `VersionedConfigHeader` is intentionally
re-declared here rather than imported from `apps.product`: foundation must
not depend on a business module (DOC-004 s3.1).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers


class RuleSetVersionRequestSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    ruleDomain = serializers.ChoiceField(
        source="rule_domain", choices=["ELIGIBILITY", "PRICING", "WORKFLOW", "VALIDATION"]
    )
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True, required=False, default=None)
    artifactType = serializers.ChoiceField(
        source="artifact_type", choices=["DRL", "DECISION_TABLE", "JSON", "INTERNAL"]
    )
    artifactRef = serializers.CharField(source="artifact_ref", allow_null=True, required=False, default=None)
    artifactChecksum = serializers.CharField(
        source="artifact_checksum", allow_null=True, required=False, default=None
    )


class RuleVersionUpdateRequestSerializer(serializers.Serializer):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6 — only DRAFT is editable;
    `code`/`ruleDomain`/`effectiveFrom`/`effectiveTo` are not editable
    fields (identity/domain/vigência of a version, not content)."""

    name = serializers.CharField()
    artifactType = serializers.ChoiceField(
        source="artifact_type", choices=["DRL", "DECISION_TABLE", "JSON", "INTERNAL"]
    )
    artifactRef = serializers.CharField(source="artifact_ref", allow_null=True, required=False, default=None)
    artifactChecksum = serializers.CharField(
        source="artifact_checksum", allow_null=True, required=False, default=None
    )


@extend_schema_serializer(component_name="RuleVersionHeader")
class VersionedConfigHeaderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.SerializerMethodField()
    versionNo = serializers.IntegerField(source="version_no", min_value=1)
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True)
    status = serializers.CharField()
    checksum = serializers.SerializerMethodField()

    def get_code(self, obj) -> str:
        return obj.rule_set.code

    def get_checksum(self, obj) -> str | None:
        return obj.artifact_checksum
