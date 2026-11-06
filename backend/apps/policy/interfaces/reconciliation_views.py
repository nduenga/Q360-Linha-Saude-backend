"""Reconciliação de extrato bancário e prévia de inclusão de beneficiários."""
from __future__ import annotations

from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.policy.application import endorsement_service, issuance_service, reconciliation_service
from apps.policy.infrastructure.models import Policy
from apps.policy.interfaces.serializers import PolicySerializer, PremiumInstallmentSerializer

MAX_STATEMENT_BYTES = 5 * 1024 * 1024


class ReconciliationLineSerializer(serializers.Serializer):
    line = serializers.IntegerField(min_value=1)
    policyId = serializers.UUIDField()
    installmentNos = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    amount = serializers.DecimalField(max_digits=30, decimal_places=2)
    paidOn = serializers.DateField()
    paymentReference = serializers.CharField(max_length=200)


class PaymentAllocationRequestSerializer(serializers.Serializer):
    installmentNos = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=12)
    amount = serializers.DecimalField(max_digits=30, decimal_places=2, min_value=Decimal("0.01"))
    paidAt = serializers.DateTimeField()
    paymentReference = serializers.CharField(required=False, default=None, allow_null=True, max_length=200)
    paymentMethod = serializers.CharField(required=False, default=None, allow_null=True, max_length=50)
    rowVersion = serializers.IntegerField(
        min_value=0, required=False, default=None, allow_null=True,
        help_text="Obrigatório quando inclui a 1.ª prestação (ativa a apólice).",
    )


class ReconciliationCommitRequestSerializer(serializers.Serializer):
    lines = ReconciliationLineSerializer(many=True, allow_empty=False)


class _DependentSerializer(serializers.Serializer):
    relationshipCode = serializers.CharField(max_length=40)
    firstName = serializers.CharField(max_length=120)
    lastName = serializers.CharField(max_length=120, required=False, allow_null=True, allow_blank=True)
    dateOfBirth = serializers.DateField()
    sexCode = serializers.CharField(max_length=20, required=False, allow_null=True)
    externalReference = serializers.CharField(max_length=100, required=False, allow_null=True)
    nif = serializers.CharField(max_length=14, required=False, allow_null=True)
    attributes = serializers.JSONField(required=False, allow_null=True)


class InclusionPreviewRequestSerializer(serializers.Serializer):
    inclusionDate = serializers.DateField()
    memberIds = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    holderMemberId = serializers.UUIDField(required=False, allow_null=True, default=None)
    dependent = _DependentSerializer(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        has_dependent = attrs["dependent"] is not None
        if has_dependent == bool(attrs["memberIds"]):
            raise serializers.ValidationError("Indique as pessoas a incluir (memberIds) ou uma pessoa nova (dependent).")
        if has_dependent and attrs["holderMemberId"] is None:
            raise serializers.ValidationError({"holderMemberId": "Indique o titular da pessoa nova."})
        return attrs


class _PaymentPermissions:
    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]


class BankStatementPreviewView(_PaymentPermissions, APIView):
    """`POST /payment-reconciliations/preview` — lê o extrato e classifica cada linha; nada é gravado."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise ValidationError({"file": "Escolha o ficheiro do extrato."})
        if uploaded.size > MAX_STATEMENT_BYTES:
            raise ValidationError({"file": "O ficheiro não pode ter mais de 5 MB."})
        return Response(reconciliation_service.preview(filename=uploaded.name, content=uploaded.read()))


@requires_idempotency
class BankStatementCommitView(_PaymentPermissions, APIView):
    """`POST /payment-reconciliations/commit` — regista as linhas confirmadas."""

    def post(self, request):
        body = ReconciliationCommitRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(reconciliation_service.commit(
            lines=body.validated_data["lines"], correlation_id=get_correlation_id(),
        ))


class PolicyPaymentOptionsView(APIView):
    """`GET /policies/{id}/payment-options` — que prestações uma transferência
    pode pagar: conjuntos seguidos, com o total de cada um."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        return Response(issuance_service.payment_options(policy))


@requires_idempotency
class PolicyPaymentAllocationView(_PaymentPermissions, APIView):
    """`POST /policies/{id}/payments` — regista uma transferência numa ou mais
    prestações seguidas; ou ficam todas pagas, ou nenhuma."""

    def post(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        body = PaymentAllocationRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated, installments = issuance_service.allocate_payment(
            policy=policy, installment_nos=data["installmentNos"], amount=data["amount"], paid_at=data["paidAt"],
            payment_reference=data["paymentReference"], payment_method=data["paymentMethod"],
            row_version=data["rowVersion"], correlation_id=get_correlation_id(),
        )
        return Response({
            **PolicySerializer(updated).data,
            "installments": PremiumInstallmentSerializer(installments, many=True).data,
        })


class PolicyInclusionPreviewView(APIView):
    """`POST /policies/{id}/endorsements/inclusions/preview` — pro rata e
    duplicados antes de confirmar; nada é gravado."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CREATE)]

    def post(self, request, policy_id):
        body = InclusionPreviewRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(endorsement_service.preview_inclusion(
            policy_id=policy_id, inclusion_date=data["inclusionDate"], member_ids=data["memberIds"],
            holder_member_id=data["holderMemberId"], dependent=data["dependent"], correlation_id=get_correlation_id(),
        ))
