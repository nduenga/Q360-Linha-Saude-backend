"""DTOs for the policy module — postdates ART-006 entirely
(DECISIONS_TAKEN.md#S09-POLICY-001), so there is no artifact schema to
match verbatim; field names follow this project's own established
camelCase convention instead."""
from __future__ import annotations

from datetime import date

from rest_framework import serializers

from shared.status_labels import status_label
from apps.pricing.domain.money import round_amount
from apps.policy.application.lifecycle_service import calculate_resolution_refund
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


class DefaultNoticeRequestSerializer(serializers.Serializer):
    registeredMailReference = serializers.CharField(min_length=1, max_length=200)
    newDeadline = serializers.DateField()
    sentAt = serializers.DateTimeField(required=False, default=None, allow_null=True)


class CancelPolicyRequestSerializer(serializers.Serializer):
    reasonCode = serializers.CharField(min_length=1, max_length=100)
    reasonText = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=2000)
    effectiveDate = serializers.DateField()


class ExcludePolicyMemberRequestSerializer(serializers.Serializer):
    effectiveDate = serializers.DateField()
    reason = serializers.CharField(min_length=10, max_length=2000)


class EmitPaymentSerializer(serializers.Serializer):
    paidAt = serializers.DateTimeField()
    paymentMethod = serializers.ChoiceField(choices=["NUMERARIO", "TRANSFERENCIA", "MULTICAIXA", "TPA"])
    paymentReference = serializers.CharField(required=False, default=None, allow_null=True, allow_blank=True, max_length=200)


class EmitPolicyRequestSerializer(IssuePolicyRequestSerializer):
    """Emissão em um só passo: assinatura + (opcional) pagamento da 1.ª prestação."""

    payment = EmitPaymentSerializer(required=False, default=None, allow_null=True)


class PolicySerializer(serializers.Serializer):
    def get_status_label(self, obj) -> str | None:
        return status_label("policy", obj.status)

    id = serializers.UUIDField()
    policyNumber = serializers.CharField(source="policy_number", allow_null=True)
    statusLabel = serializers.SerializerMethodField(method_name="get_status_label")
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
    resolvedByLaw = serializers.BooleanField(source="resolved_by_law")
    resolvedAt = serializers.DateTimeField(source="resolved_at", allow_null=True)
    resolvedEffectiveFrom = serializers.DateField(source="resolved_effective_from", allow_null=True)
    resolutionReason = serializers.CharField(source="resolution_reason_code", allow_null=True)
    legalBasis = serializers.CharField(source="legal_basis", allow_null=True)
    refundAmount = serializers.SerializerMethodField(method_name="get_refund_amount")
    refundCurrencyCode = serializers.CharField(source="currency_code", allow_null=True)
    refundEffectivePeriodStart = serializers.SerializerMethodField(method_name="get_refund_effective_period_start")
    refundEffectivePeriodEnd = serializers.SerializerMethodField(method_name="get_refund_effective_period_end")
    refundStatus = serializers.SerializerMethodField(method_name="get_refund_status")
    rowVersion = serializers.IntegerField(source="row_version")
    # Pragmatic addition: só para mostrar nomes em vez de ids na UI.
    proposerName = serializers.SerializerMethodField(method_name="get_proposer_name")
    planName = serializers.SerializerMethodField(method_name="get_plan_name")

    def get_proposer_name(self, obj) -> str | None:
        proposer = getattr(obj, "proposer", None)
        return proposer.display_name if proposer else None

    def get_plan_name(self, obj) -> str | None:
        plan = getattr(obj, "plan", None)
        return plan.name if plan else None

    def _refund(self, obj) -> dict:
        cache = getattr(self, "_resolution_refunds", None)
        if cache is None:
            cache = self._resolution_refunds = {}
        key = str(obj.pk)
        if key not in cache:
            cache[key] = calculate_resolution_refund(obj)
        return cache[key]

    def get_refund_amount(self, obj) -> str | None:
        amount = self._refund(obj)["amount"]
        return str(amount) if amount is not None else None

    def get_refund_effective_period_start(self, obj) -> date | None:
        return self._refund(obj)["period_start"]

    def get_refund_effective_period_end(self, obj) -> date | None:
        return self._refund(obj)["period_end"]

    def get_refund_status(self, obj) -> str:
        return self._refund(obj)["status"]


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
    paymentBatchId = serializers.UUIDField(source="payment_batch_id", allow_null=True)
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


class MemberDocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="PDF, JPG ou PNG, até 10 MB.")
    evidenceType = serializers.ChoiceField(
        choices=["ENROLLMENT_CERTIFICATE", "UNION_HOMOLOGATION", "DEPENDENCY_PROOF", "OTHER"],
        help_text="Que documento é: certificado de matrícula, comprovativo de união, prova de dependência ou outro.",
    )
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)
    unionBondType = serializers.ChoiceField(
        choices=["UNIAO_DE_FACTO", "CASAMENTO_CIVIL"], required=False,
        help_text="Só em UNION_HOMOLOGATION: tipo de união que o documento comprova.",
    )


class MemberDocumentReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["APPROVE", "REJECT"])
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)
