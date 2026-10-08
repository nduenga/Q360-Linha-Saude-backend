"""Controllers for the policy module — postdates ART-006 entirely
(DECISIONS_TAKEN.md#S09-POLICY-001/003). Permission reuse (no new
`Permission` enum values — `apps.foundation.domain.permissions` forbids
inventing one without an approved DOC-001 s18 entry): both issuing a
policy and registering its first premium payment are gated by
`Scope.APPROVE` + `Permission.QUOTE_APPROVE` — the same persona that
decided the quote is the one who carries it through signature and
activation in this phase. A dedicated back-office/finance permission for
day-to-day payment registration (distinct from underwriting approval) is
future work, not invented here without an approved DOC-001 entry."""
from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.policy.application import emission_service, policy_document
from apps.policy.application.issuance_service import issue_policy, register_first_premium_payment
from apps.policy.infrastructure.models import Policy, PolicyMember, PolicySignature, PremiumInstallment
from apps.policy.interfaces.serializers import (
    EmitPolicyRequestSerializer,
    IssuePolicyRequestSerializer,
    PolicyMemberSerializer,
    PolicySerializer,
    PolicySignatureSerializer,
    PremiumInstallmentSerializer,
    RegisterFirstPremiumPaymentRequestSerializer,
)
from apps.quote.infrastructure.models import Quote
from shared.pagination import Q360PageNumberPagination


@requires_idempotency
class IssuePolicyView(APIView):
    """`POST /api/v1/quotes/{quoteId}/policy` — PO-APO-1: the moment the
    tomador's signature turns a Quote into a contract."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = IssuePolicyRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        policy = issue_policy(
            quote=quote,
            signatory_name=data["signatoryName"],
            signatory_document_type=data["signatoryDocumentType"],
            signatory_document_number=data["signatoryDocumentNumber"],
            signatory_capacity=data["signatoryCapacity"],
            signature_method=data["signatureMethod"],
            signed_at=data["signedAt"],
            term_months=data["termMonths"],
            payment_frequency=data["paymentFrequency"],
            requested_start_date=data["requestedStartDate"],
            row_version=data["rowVersion"],
            correlation_id=get_correlation_id(),
        )
        return Response(PolicySerializer(policy).data, status=201)


class PolicyListView(APIView):
    """`GET /api/v1/policies` — pragmatic addition, not backed by any
    artifact (this module postdates ART-006 entirely). `?policyNumber=`
    mirrors the same lookup-by-number pragmatic filter `apps.quote`
    already has for quotes."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        queryset = Policy.objects.all().order_by("-created_at")
        policy_number = request.query_params.get("policyNumber")
        if policy_number:
            queryset = queryset.filter(policy_number=policy_number)
        proposer_id = request.query_params.get("proposerId")
        if proposer_id:
            queryset = queryset.filter(proposer_id=proposer_id)
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(PolicySerializer(page, many=True).data)


class PolicyDetailView(APIView):
    """`GET /api/v1/policies/{policyId}`."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        return Response(PolicySerializer(policy).data)


class PolicyMemberListView(APIView):
    """`GET /api/v1/policies/{policyId}/members`."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        queryset = PolicyMember.objects.filter(policy=policy).order_by("created_at")
        return Response(PolicyMemberSerializer(queryset, many=True).data)


class PolicySignatureView(APIView):
    """`GET /api/v1/policies/{policyId}/signature`."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        signature = get_object_or_404(PolicySignature, policy=policy)
        return Response(PolicySignatureSerializer(signature).data)


class PolicyInstallmentListView(APIView):
    """`GET /api/v1/policies/{policyId}/installments`."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        queryset = PremiumInstallment.objects.filter(policy=policy).order_by("installment_no")
        return Response(PremiumInstallmentSerializer(queryset, many=True).data)


@requires_idempotency
class RegisterFirstPremiumPaymentView(APIView):
    """`POST /api/v1/policies/{policyId}/installments/1/payment` — Decreto
    2/02 art. 17.º: the 1.ª fracção turns `PENDING_FIRST_PREMIUM` into
    `ACTIVE` and starts the risk (ROADMAP_APOLICES.md Fase 3). Only the
    first installment is handled here — recurring installments/suspension
    for missed payments are Fase 7, not yet built."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, policy_id, installment_no):
        policy = get_object_or_404(Policy, id=policy_id)
        if installment_no != 1:
            from apps.policy.domain.errors import ReferencedEntityNotFoundError

            raise ReferencedEntityNotFoundError(
                "Only the first installment can be registered here — recurring installment payments "
                "are not yet built (ROADMAP_APOLICES.md Fase 7)"
            )
        body = RegisterFirstPremiumPaymentRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = register_first_premium_payment(
            policy=policy,
            paid_at=data["paidAt"],
            payment_reference=data["paymentReference"],
            payment_method=data["paymentMethod"],
            row_version=data["rowVersion"],
            correlation_id=get_correlation_id(),
        )
        return Response(PolicySerializer(updated).data)


class PolicyDraftView(APIView):
    """`GET /api/v1/quotes/{quoteId}/policy-draft` — o ecrã de emissão do GTE:
    todos os termos da apólice já preenchidos a partir da cotação aprovada
    (titular, plano, prémio, prestações, pessoas seguras, coberturas, franquia,
    carências, exclusões) e os valores por omissão de assinatura e pagamento."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(emission_service.build_draft(quote))


@requires_idempotency
class EmitPolicyView(APIView):
    """`POST /api/v1/quotes/{quoteId}/policy/emit` — emite a apólice num só
    passo: regista a assinatura presencial, (opcionalmente) o pagamento da
    1.ª prestação e gera a apólice digital. Sem `payment`, a apólice fica a
    aguardar o pagamento."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = EmitPolicyRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        policy = emission_service.emit_policy(
            quote=quote,
            signatory_name=data["signatoryName"],
            signatory_document_type=data["signatoryDocumentType"],
            signatory_document_number=data["signatoryDocumentNumber"],
            signatory_capacity=data["signatoryCapacity"],
            signature_method=data["signatureMethod"],
            signed_at=data["signedAt"],
            term_months=data["termMonths"],
            payment_frequency=data["paymentFrequency"],
            requested_start_date=data["requestedStartDate"],
            row_version=data["rowVersion"],
            payment=data["payment"],
            correlation_id=get_correlation_id(),
        )
        payload = dict(PolicySerializer(policy).data)
        payload["documentPath"] = f"/api/v1/policies/{policy.id}/document"
        return Response(payload, status=201)


class PolicyDocumentView(APIView):
    """`GET /api/v1/policies/{policyId}/document?fileType=pdf|html|docx` — a
    apólice digital."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id)
        data, content_type, name = policy_document.policy_document(policy, request.query_params.get("fileType", "pdf"))
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{name}"'
        return response
