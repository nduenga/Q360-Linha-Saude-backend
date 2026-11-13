"""Questionário clínico, atribuição de revisões, cotação numa página, anulação
do envio e renovações em lote (Manual visual v2)."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.pricing.interfaces.serializers import render_preview
from apps.quote.application import (
    questionnaire_service,
    renewal_worklist_service,
    review_service,
    workspace_service,
)
from apps.quote.infrastructure.models import Quote, ReviewTask
from apps.quote.interfaces.serializers import ReviewTaskSerializer, review_task_context
from shared.pagination import Q360PageNumberPagination


class QuestionnaireSaveRequestSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.JSONField(allow_null=True), required=False, default=dict)
    currentSection = serializers.CharField(required=False, allow_null=True, default=None, max_length=40)
    rowVersion = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=0)


class QuestionnaireCompleteRequestSerializer(serializers.Serializer):
    rowVersion = serializers.IntegerField(min_value=0)


class ReviewAssignRequestSerializer(serializers.Serializer):
    assigneeId = serializers.UUIDField(required=False, allow_null=True, default=None)


class ReviewAssignBatchRequestSerializer(ReviewAssignRequestSerializer):
    taskIds = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=review_service.MAX_BATCH,
    )


class ReviewDecisionBatchRequestSerializer(serializers.Serializer):
    taskIds = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=review_service.MAX_BATCH,
    )
    decision = serializers.ChoiceField(choices=["APPROVE", "REJECT", "RETURN"])
    reasonCode = serializers.CharField(min_length=1, max_length=100)
    reasonText = serializers.CharField(allow_null=True, allow_blank=True, required=False, default=None)


class QuoteWorkspaceRequestSerializer(serializers.Serializer):
    memberIds = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)
    selection = serializers.JSONField(required=False, allow_null=True, default=None)
    rowVersion = serializers.IntegerField(min_value=0)


class RenewalBatchRequestSerializer(serializers.Serializer):
    policyIds = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=renewal_worklist_service.MAX_BATCH,
    )


class QuoteQuestionnaireListView(APIView):
    """`GET /quotes/{id}/questionnaires` — estado do questionário de cada pessoa,
    sem as respostas."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, quote_id):
        """Devolve o estado e o progresso dos questionários, sem respostas clínicas."""
        quote = get_object_or_404(Quote, id=quote_id)
        return Response({"items": questionnaire_service.list_for_quote(quote)})


class QuoteMemberQuestionnaireView(APIView):
    """`GET`/`PUT /quotes/{id}/members/{memberId}/questionnaire` — lê ou guarda o
    progresso. As respostas são dados de saúde: só perfis que revêem cotações."""

    def get_permissions(self):
        if self.request.method == "GET":
            return [require_scope(Scope.READ)(), require_permission(Permission.QUOTE_REVIEW)()]
        return [require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_REVIEW)()]

    def get(self, request, quote_id, member_id):
        """Devolve o questionário e a definição versionada usada neste preenchimento."""
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(questionnaire_service.detail(quote, member_id))

    def put(self, request, quote_id, member_id):
        """Guarda respostas parciais com controlo de concorrência por rowVersion."""
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuestionnaireSaveRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(questionnaire_service.save(
            quote=quote, member_id=member_id, answers=data["answers"], current_section=data["currentSection"],
            row_version=data["rowVersion"],
        ))


@requires_idempotency
class QuoteMemberQuestionnaireCompleteView(APIView):
    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_REVIEW)]

    def post(self, request, quote_id, member_id):
        """Conclui o questionário se todas as respostas obrigatórias estiverem preenchidas."""
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuestionnaireCompleteRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(questionnaire_service.complete(
            quote=quote, member_id=member_id, row_version=body.validated_data["rowVersion"],
        ))


@requires_idempotency
class QuoteMemberQuestionnaireRequestView(APIView):
    """`POST .../questionnaire/customer-request` — pede o preenchimento ao cliente no Portal."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_EDIT)]

    def post(self, request, quote_id, member_id):
        """Pede ao cliente que preencha este questionário no Portal."""
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(questionnaire_service.request_from_customer(quote=quote, member_id=member_id))


class _ReviewPermissions:
    permission_classes = [require_scope(Scope.APPROVE), require_permission(Permission.QUOTE_REVIEW)]


@requires_idempotency
class ReviewAssignmentView(_ReviewPermissions, APIView):
    """`POST /reviews/{id}/assignment` — sem `assigneeId`, atribui a quem pede."""

    def post(self, request, task_id):
        task = get_object_or_404(ReviewTask.objects.select_related("quote__proposer", "quote__plan__product"), id=task_id)
        body = ReviewAssignRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = review_service.assign(task=task, assignee_id=body.validated_data["assigneeId"])
        return Response(ReviewTaskSerializer(updated, context=review_task_context([updated])).data)


@requires_idempotency
@requires_idempotency
class ReviewBatchDecisionView(APIView):
    """`POST /reviews/decisions` — decisão em lote, com resultado por cotação."""

    permission_classes = [require_scope(Scope.APPROVE)]

    def post(self, request):
        from apps.foundation.application.permission_evaluator import PermissionEvaluator
        from apps.quote.interfaces.views import _DECISION_PERMISSION

        body = ReviewDecisionBatchRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        actor = getattr(getattr(request, "user", None), "actor", None)
        return Response(review_service.decide_many(
            task_ids=data["taskIds"], decision=data["decision"], reason_code=data["reasonCode"],
            reason_text=data["reasonText"], correlation_id=get_correlation_id(),
            can_decide=lambda decision: PermissionEvaluator.is_authorised(actor, _DECISION_PERMISSION[decision]),
        ))


class ReviewBatchAssignmentView(_ReviewPermissions, APIView):
    """`POST /reviews/assignments` — atribuição em lote; cada tarefa é independente."""

    def post(self, request):
        body = ReviewAssignBatchRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        result = review_service.assign_many(task_ids=data["taskIds"], assignee_id=data["assigneeId"])
        assigned = result["assigned"]
        return Response({
            "assigned": ReviewTaskSerializer(assigned, many=True, context=review_task_context(assigned)).data,
            "failed": result["failed"],
        })


class ReviewEligibleReviewersView(_ReviewPermissions, APIView):
    def get(self, request, task_id):
        task = get_object_or_404(ReviewTask.objects.select_related("quote"), id=task_id)
        return Response(review_service.eligibility_report(task.quote))


class QuoteWorkspaceView(APIView):
    """`GET`/`PUT /quotes/{id}/workspace` — a cotação numa só página. O `PUT` é a
    gravação automática: guarda pessoas e opções, verifica a elegibilidade e
    recalcula; uma falha de cálculo vem em `pricingError` e nada se perde."""

    def get_permissions(self):
        if self.request.method == "GET":
            return [require_scope(Scope.READ)()]
        return [
            require_scope(Scope.WRITE)(), require_permission(Permission.QUOTE_EDIT)(),
            require_permission(Permission.QUOTE_CALCULATE)(),
        ]

    def get(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        return Response(workspace_service.snapshot(quote, render=render_preview))

    def put(self, request, quote_id):
        quote = get_object_or_404(Quote, id=quote_id)
        body = QuoteWorkspaceRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(workspace_service.sync(
            quote=quote, member_ids=data["memberIds"], selection=data["selection"], row_version=data["rowVersion"],
            correlation_id=get_correlation_id(), render=render_preview,
        ))


class RenewalDueListView(APIView):
    """`GET /renewals/due?days=30` — apólices a vencer, com sinistralidade e prémio proposto."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", "30"))
        except ValueError as exc:
            raise ValidationError({"days": "Indique um número de dias."}) from exc
        if not 1 <= days <= 365:
            raise ValidationError({"days": "O horizonte tem de estar entre 1 e 365 dias."})
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(renewal_worklist_service.due_policies(days=days), request)
        return paginator.get_paginated_response([renewal_worklist_service.worklist_row(policy) for policy in page])


@requires_idempotency
class QuoteRenewalBatchView(APIView):
    """`POST /quotes/renewals/batch` — cria os rascunhos; cada apólice é independente."""

    permission_classes = [require_scope(Scope.WRITE), require_permission(Permission.QUOTE_CREATE)]

    def post(self, request):
        body = RenewalBatchRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(renewal_worklist_service.create_batch(policy_ids=body.validated_data["policyIds"]))
