"""DTOs matching ART-006 `Quote`/`QuoteCreateRequest`/`QuoteUpdateRequest`/
`QuoteMemberRequest`/`QuotePriceRequest` verbatim (see
apps/product/interfaces/serializers.py for the general "why plain
Serializer" rationale).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.quote.domain.enums import QuoteStatus


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
