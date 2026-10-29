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
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.policy.application import emission_service, lifecycle_service, policy_document
from apps.policy.application.issuance_service import (
    issue_policy,
    register_first_premium_payment,
    register_installment_payment,
)
from apps.policy.infrastructure.models import Policy, PolicyMember, PolicySignature, PremiumInstallment
from apps.policy.interfaces.serializers import (
    EmitPolicyRequestSerializer,
    IssuePolicyRequestSerializer,
    PolicyMemberSerializer,
    PolicySerializer,
    PolicySignatureSerializer,
    PremiumInstallmentSerializer,
    RegisterFirstPremiumPaymentRequestSerializer,
    DefaultNoticeRequestSerializer,
    CancelPolicyRequestSerializer,
    ExcludePolicyMemberRequestSerializer,
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
    """`POST /api/v1/policies/{policyId}/installments/{n}/payment` — regista o
    pagamento de uma prestação.

    * n = 1: Decreto 2/02 art. 17.º, a 1.ª fração passa `PENDING_FIRST_PREMIUM`
      a `ACTIVE` e começa o risco (exige `rowVersion`).
    * n >= 2: apólice ativa; as prestações pagam-se por ordem.

    A suspensão por falta de pagamento (Fase 7) ainda não existe."""

    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, policy_id, installment_no):
        policy = get_object_or_404(Policy, id=policy_id)
        body = RegisterFirstPremiumPaymentRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if installment_no != 1:
            installment = register_installment_payment(
                policy=policy,
                installment_no=installment_no,
                paid_at=data["paidAt"],
                payment_reference=data["paymentReference"],
                payment_method=data["paymentMethod"],
                correlation_id=get_correlation_id(),
            )
            policy.refresh_from_db()
            payload = dict(PolicySerializer(policy).data)
            payload["installment"] = PremiumInstallmentSerializer(installment).data
            return Response(payload)
        if data["rowVersion"] is None:
            raise ValidationError({"rowVersion": "A versão (rowVersion) é obrigatória ao registar a 1.ª prestação."})
        updated = register_first_premium_payment(
            policy=policy,
            paid_at=data["paidAt"],
            payment_reference=data["paymentReference"],
            payment_method=data["paymentMethod"],
            row_version=data["rowVersion"],
            correlation_id=get_correlation_id(),
        )
        payload = dict(PolicySerializer(updated).data)
        payload["installment"] = PremiumInstallmentSerializer(
            PremiumInstallment.objects.get(policy=updated, installment_no=1)
        ).data
        return Response(payload)


@requires_idempotency
class PolicyDefaultNoticeView(APIView):
    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, policy_id, installment_no):
        policy = get_object_or_404(Policy, id=policy_id)
        body = DefaultNoticeRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        notice = lifecycle_service.register_default_notice(
            policy=policy, installment_no=installment_no,
            registered_mail_reference=data["registeredMailReference"], new_deadline=data["newDeadline"],
            sent_at=data["sentAt"],
        )
        return Response({"id": str(notice.id), "installmentNo": installment_no,
                         "newDeadline": notice.new_deadline, "status": "NOTICE_REGISTERED"}, status=201)


@requires_idempotency
class PolicySuspendView(APIView):
    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, policy_id, installment_no):
        policy = lifecycle_service.suspend_for_default(
            policy=get_object_or_404(Policy, id=policy_id), installment_no=installment_no,
            correlation_id=get_correlation_id(),
        )
        return Response(PolicySerializer(policy).data)


@requires_idempotency
class PolicyTerminateView(APIView):
    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, policy_id, installment_no):
        policy = lifecycle_service.terminate_for_default(
            policy=get_object_or_404(Policy, id=policy_id), installment_no=installment_no,
            correlation_id=get_correlation_id(),
        )
        return Response(PolicySerializer(policy).data)


@requires_idempotency
class PolicyCancelView(APIView):
    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_APPROVE)]

    def post(self, request, policy_id):
        body = CancelPolicyRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        policy = lifecycle_service.cancel_policy(policy=get_object_or_404(Policy, id=policy_id),
            reason_code=data["reasonCode"], reason_text=data["reasonText"], effective_date=data["effectiveDate"],
            correlation_id=get_correlation_id())
        return Response(PolicySerializer(policy).data)


@requires_idempotency
class PolicyMemberExcludeView(APIView):
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def post(self, request, policy_id, member_id):
        body = ExcludePolicyMemberRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        member = lifecycle_service.exclude_member(policy=get_object_or_404(Policy, id=policy_id), member_id=member_id,
            effective_date=data["effectiveDate"], reason=data["reason"], correlation_id=get_correlation_id())
        return Response(PolicyMemberSerializer(member).data)


class InstallmentListView(APIView):
    """`GET /api/v1/installments` — cobranças: as prestações de todas as
    apólices, para o GTE ver o que está por pagar e registar pagamentos.

    Filtros: `status` (DUE, OVERDUE, PAID), `dueBefore` (AAAA-MM-DD),
    `policyNumber`, `q` (nome do tomador). Atrasadas = por pagar e com
    vencimento já passado."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        import datetime

        from apps.client.infrastructure.models import Proposer
        from apps.policy.application.issuance_service import effective_installment_status

        today = datetime.date.today()
        queryset = PremiumInstallment.objects.select_related("policy").exclude(status="VOID").order_by("due_date", "installment_no")
        status_filter = request.query_params.get("status")
        if status_filter == "OVERDUE":
            queryset = queryset.filter(status__in=("DUE", "OVERDUE"), due_date__lt=today)
        elif status_filter == "DUE":
            queryset = queryset.filter(status="DUE", due_date__gte=today)
        elif status_filter == "PAID":
            queryset = queryset.filter(status="PAID")
        elif status_filter:
            raise ValidationError({"status": "O estado tem de ser DUE, OVERDUE ou PAID."})
        due_before = request.query_params.get("dueBefore")
        if due_before:
            try:
                queryset = queryset.filter(due_date__lte=datetime.date.fromisoformat(due_before))
            except ValueError as exc:
                raise ValidationError({"dueBefore": "A data tem de estar no formato AAAA-MM-DD."}) from exc
        policy_number = request.query_params.get("policyNumber")
        if policy_number:
            queryset = queryset.filter(policy__policy_number=policy_number)
        search = (request.query_params.get("q") or "").strip()
        if search:
            holder_ids = Proposer.objects.filter(display_name__icontains=search).values_list("id", flat=True)
            queryset = queryset.filter(policy__proposer_id__in=list(holder_ids))
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        holders = dict(
            Proposer.objects.filter(id__in={i.policy.proposer_id for i in page}).values_list("id", "display_name")
        )
        items = []
        for installment in page:
            effective = effective_installment_status(installment, today)
            items.append(
                {
                    **PremiumInstallmentSerializer(installment).data,
                    "status": effective,
                    "policyId": str(installment.policy_id),
                    "policyNumber": installment.policy.policy_number,
                    "policyStatus": installment.policy.status,
                    "holderName": holders.get(installment.policy.proposer_id),
                    "daysOverdue": (today - installment.due_date).days if effective == "OVERDUE" else 0,
                    "canRegisterPayment": effective in ("DUE", "OVERDUE") and installment.policy.status == "ACTIVE",
                }
            )
        return paginator.get_paginated_response(items)


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
