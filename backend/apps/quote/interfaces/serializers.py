"""DTOs matching ART-006 `Quote`/`QuoteCreateRequest`/`QuoteUpdateRequest`/
`QuoteMemberRequest`/`QuotePriceRequest` verbatim (see
apps/product/interfaces/serializers.py for the general "why plain
Serializer" rationale).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.quote.domain.enums import (
    DocumentStatus,
    DocumentTemplateStatus,
    DocumentType,
    QuoteDecisionType,
    QuoteStatus,
    ReviewTaskStatus,
)


class QuoteSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quoteNumber = serializers.CharField(source="quote_number", allow_null=True)
    proposerId = serializers.UUIDField(source="proposer_id")
    productVersionId = serializers.UUIDField(source="product_version_id")
    planId = serializers.UUIDField(source="plan_id")
    status = serializers.ChoiceField(choices=[s.value for s in QuoteStatus])
    effectiveDate = serializers.DateField(source="effective_date")
    validUntil = serializers.DateField(source="valid_until", allow_null=True)
    currencyCode = serializers.CharField(source="currency_code", allow_null=True)
    latestPricingRunId = serializers.UUIDField(source="latest_pricing_run_id", allow_null=True)
    rowVersion = serializers.IntegerField(source="row_version")


class QuoteCreateRequestSerializer(serializers.Serializer):
    proposerId = serializers.UUIDField()
    productVersionId = serializers.UUIDField()
    planId = serializers.UUIDField()
    effectiveDate = serializers.DateField()


class QuoteUpdateRequestSerializer(serializers.Serializer):
    effectiveDate = serializers.DateField()
    rowVersion = serializers.IntegerField(min_value=0)


class QuoteMemberRequestSerializer(serializers.Serializer):
    memberId = serializers.UUIDField()


class QuotePriceRequestSerializer(serializers.Serializer):
    recalculate = serializers.BooleanField(required=False, default=False)


class QuoteMemberSerializer(serializers.Serializer):
    """Pragmatic V1 addition (`GET /quotes/{quoteId}/members`, not in
    ART-006 — see OPEN_DECISIONS.md#S04-LISTING-GAPS-001/DECISIONS_TAKEN.md):
    `Quote` itself has no population field, so the frontend needs a real
    way to see who is on the quote."""

    id = serializers.UUIDField()
    memberId = serializers.UUIDField(source="member_id")
    status = serializers.CharField()
    eligibilityEvaluationId = serializers.UUIDField(source="eligibility_evaluation_id", allow_null=True)


class QuoteSubmitRequestSerializer(serializers.Serializer):
    rowVersion = serializers.IntegerField(min_value=0)


class DecisionRequestSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[d.value for d in QuoteDecisionType])
    reasonCode = serializers.CharField(min_length=1, max_length=100, source="reason_code")
    reasonText = serializers.CharField(source="reason_text", allow_null=True, required=False, default=None)
    rowVersion = serializers.IntegerField(min_value=0)


class ReviewTaskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    status = serializers.ChoiceField(choices=[s.value for s in ReviewTaskStatus])
    assignedTo = serializers.CharField(source="assigned_to", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at")


class StateHistoryItemSerializer(serializers.Serializer):
    fromStatus = serializers.CharField(source="from_status", allow_null=True)
    toStatus = serializers.CharField(source="to_status")
    reasonCode = serializers.CharField(source="reason_code", allow_null=True)
    reasonText = serializers.CharField(source="reason_text", allow_null=True)
    changedBy = serializers.CharField(source="changed_by")
    changedAt = serializers.DateTimeField(source="changed_at")


class CancelQuoteRequestSerializer(serializers.Serializer):
    reasonCode = serializers.CharField(min_length=1, max_length=100, source="reason_code")
    reasonText = serializers.CharField(source="reason_text", allow_null=True, required=False, default=None)
    rowVersion = serializers.IntegerField(min_value=0)


class DocumentSerializer(serializers.Serializer):
    """DTO matching ART-006 `Document` verbatim."""

    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    documentType = serializers.ChoiceField(source="document_type", choices=[t.value for t in DocumentType])
    documentNumber = serializers.CharField(source="document_number", allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in DocumentStatus])
    generatedAt = serializers.DateTimeField(source="generated_at", allow_null=True)


class DocumentTemplateCreateRequestSerializer(serializers.Serializer):
    """Pragmatic V1 addition, not in ART-006 (see
    apps/quote/application/document_service.py module docstring)."""

    templateCode = serializers.CharField(source="template_code")
    storageRef = serializers.CharField(source="storage_ref")
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True, required=False, default=None)


class DocumentTemplateUpdateRequestSerializer(serializers.Serializer):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6 — only DRAFT is editable;
    `templateCode`/`effectiveFrom`/`effectiveTo` are not editable fields."""

    storageRef = serializers.CharField(source="storage_ref")


class DocumentTemplateHeaderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    templateCode = serializers.CharField(source="template_code")
    versionNo = serializers.IntegerField(source="version_no")
    status = serializers.ChoiceField(choices=[s.value for s in DocumentTemplateStatus])
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True)
    checksum = serializers.CharField(allow_null=True)
