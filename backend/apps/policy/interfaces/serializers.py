"""DTOs for the policy module — postdates ART-006 entirely
(DECISIONS_TAKEN.md#S09-POLICY-001), so there is no artifact schema to
match verbatim; field names follow this project's own established
camelCase convention instead."""
from __future__ import annotations

from rest_framework import serializers

from apps.pricing.domain.money import round_amount
from apps.policy.domain.enums import (
    PolicyMemberStatus,
    PolicyStatus,
    PolicyType,
    SignatoryCapacity,
    SignatoryDocumentType,
    SignatureMethod,
)


class IssuePolicyRequestSerializer(serializers.Serializer):
    signatoryName = serializers.CharField(min_length=1, max_length=250)
    signatoryDocumentType = serializers.ChoiceField(choices=[t.value for t in SignatoryDocumentType])
    signatoryDocumentNumber = serializers.CharField(min_length=1, max_length=100)
    signatoryCapacity = serializers.ChoiceField(choices=[c.value for c in SignatoryCapacity])
    signatureMethod = serializers.ChoiceField(
        choices=[SignatureMethod.PRESENCIAL.value], default=SignatureMethod.PRESENCIAL.value
    )
    signedAt = serializers.DateTimeField()
    termMonths = serializers.IntegerField(min_value=1)
    paymentFrequency = serializers.ChoiceField(choices=["ANUAL", "SEMESTRAL", "TRIMESTRAL", "MENSAL"])
    requestedStartDate = serializers.DateField(required=False, default=None, allow_null=True)
    rowVersion = serializers.IntegerField(min_value=0)


class RegisterFirstPremiumPaymentRequestSerializer(serializers.Serializer):
    paidAt = serializers.DateTimeField()
    paymentReference = serializers.CharField(required=False, default=None, allow_null=True, max_length=200)
    paymentMethod = serializers.CharField(required=False, default=None, allow_null=True, max_length=50)
    rowVersion = serializers.IntegerField(
        min_value=0, required=False, default=None, allow_null=True,
        help_text="Obrigatório na 1.ª prestação (ativa a apólice); ignorado nas seguintes.",
    )


class EmitPaymentSerializer(serializers.Serializer):
    paidAt = serializers.DateTimeField()
    paymentMethod = serializers.ChoiceField(choices=["NUMERARIO", "TRANSFERENCIA", "MULTICAIXA", "TPA"])
    paymentReference = serializers.CharField(required=False, default=None, allow_null=True, allow_blank=True, max_length=200)


class EmitPolicyRequestSerializer(IssuePolicyRequestSerializer):
    """Emissão em um só passo: assinatura + (opcional) pagamento da 1.ª prestação."""

    payment = EmitPaymentSerializer(required=False, default=None, allow_null=True)


class PolicySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    policyNumber = serializers.CharField(source="policy_number", allow_null=True)
    sourceQuoteId = serializers.UUIDField(source="source_quote_id")
    proposerId = serializers.UUIDField(source="proposer_id")
    planId = serializers.UUIDField(source="plan_id")
    policyType = serializers.ChoiceField(source="policy_type", choices=[t.value for t in PolicyType])
    termMonths = serializers.IntegerField(source="term_months")
    startDate = serializers.DateField(source="start_date", allow_null=True)
    endDate = serializers.DateField(source="end_date", allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in PolicyStatus])
    paymentFrequency = serializers.CharField(source="payment_frequency")
    currencyCode = serializers.CharField(source="currency_code", allow_null=True)
    rowVersion = serializers.IntegerField(source="row_version")


class PolicyMemberSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    memberId = serializers.UUIDField(source="member_id")
    status = serializers.ChoiceField(choices=[s.value for s in PolicyMemberStatus])
    pendingReasonCode = serializers.CharField(source="pending_reason_code", allow_null=True)
    inclusionDate = serializers.DateField(source="inclusion_date", allow_null=True)
    exclusionDate = serializers.DateField(source="exclusion_date", allow_null=True)
    waitingPeriodEndsJson = serializers.JSONField(source="waiting_period_ends_json")
    loadingPercentage = serializers.CharField(source="loading_percentage", allow_null=True)
    rowVersion = serializers.IntegerField(source="row_version")


class PremiumInstallmentSerializer(serializers.Serializer):
    """`amount` is stored `numeric(30,8)` (same convention as
    `apps.pricing`) — re-rounded at the serialization boundary so the API
    always shows the rounding policy's real precision."""

    id = serializers.UUIDField()
    installmentNo = serializers.IntegerField(source="installment_no")
    periodFrom = serializers.DateField(source="period_from")
    periodTo = serializers.DateField(source="period_to")
    dueDate = serializers.DateField(source="due_date")
    amount = serializers.SerializerMethodField()
    currencyCode = serializers.CharField(source="currency_code")
    status = serializers.CharField()
    paidAt = serializers.DateTimeField(source="paid_at", allow_null=True)
    paymentReference = serializers.CharField(source="payment_reference", allow_null=True)
    paymentMethod = serializers.CharField(source="payment_method", allow_null=True)

    def get_amount(self, obj) -> str:
        return str(round_amount(obj.amount))


class PolicySignatureSerializer(serializers.Serializer):
    signatoryName = serializers.CharField(source="signatory_name")
    signatoryDocumentType = serializers.CharField(source="signatory_document_type")
    signatoryDocumentNumber = serializers.CharField(source="signatory_document_number")
    signatoryCapacity = serializers.CharField(source="signatory_capacity")
    signatureMethod = serializers.CharField(source="signature_method")
    signedAt = serializers.DateTimeField(source="signed_at")
