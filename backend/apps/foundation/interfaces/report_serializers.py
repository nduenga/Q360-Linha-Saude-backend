from __future__ import annotations

from rest_framework import serializers


class TopProductReportRowSerializer(serializers.Serializer):
    productId = serializers.UUIDField()
    productName = serializers.CharField()
    quoteCount = serializers.IntegerField()
    issuedCount = serializers.IntegerField()


class TopCoverageReportRowSerializer(serializers.Serializer):
    benefitId = serializers.UUIDField()
    benefitName = serializers.CharField()
    category = serializers.CharField()
    planCount = serializers.IntegerField()


class ReportStatusCountSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class IssuanceReportSerializer(serializers.Serializer):
    totalQuotes = serializers.IntegerField()
    totalPolicies = serializers.IntegerField()
    quotesByStatus = ReportStatusCountSerializer(many=True)
    policiesByStatus = ReportStatusCountSerializer(many=True)
