"""Endpoints do cliente: pedidos, mensagens, notificações, renovação e
comparação de planos (PDF s.8, 11, 12, 14, 15). Mesma autenticação e mesmo
âmbito que `portal_views.py`; a lógica vive em `application/`."""
from __future__ import annotations

import uuid

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application import messages_service, notifications_service, renewal_service, requests_service
from apps.customer_portal.domain import requests as rules
from apps.customer_portal.interfaces.authentication import CustomerPortalJwtAuthentication
from apps.customer_portal.interfaces.comm_serializers import CreateRequestSerializer, MarkReadSerializer, MessageSerializer
from apps.customer_portal.interfaces.permissions import IsCustomerPortalActor
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.interfaces.middleware import requires_idempotency


def _account_id() -> uuid.UUID:
    actor = CurrentActorProvider.get()
    return uuid.UUID(actor.actor_id)


class _PortalView(APIView):
    authentication_classes = [CustomerPortalJwtAuthentication]
    permission_classes = [IsCustomerPortalActor]


@requires_idempotency
class CustomerPortalRequestsView(_PortalView):
    def get(self, request):
        status = request.query_params.get("status")
        if status and status not in rules.STATUS_LABELS:
            raise ValidationError({"status": f"Must be one of {sorted(rules.STATUS_LABELS)}."})
        return Response({"requests": requests_service.list_my_requests(status=status)})

    def post(self, request):
        body = CreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        created = requests_service.create_request(
            account_id=_account_id(), request_type=data["requestType"], subject=data["subject"],
            description=data["description"], policy_number=data["policyNumber"], quote_number=data["quoteNumber"],
            payload=data["payload"],
        )
        return Response(requests_service.get_my_request(created.request_number), status=201)


class CustomerPortalRequestDetailView(_PortalView):
    def get(self, request, request_number: str):
        return Response(requests_service.get_my_request(request_number))


class CustomerPortalRequestTypesView(_PortalView):
    def get(self, request):
        return Response(
            {
                "types": [
                    {
                        "code": code, "label": spec["label"], "needsPolicy": spec["policy"], "needsQuote": spec["quote"],
                        # Pedidos que o cliente resolve sozinho (descarrega o documento): ver `selfServiceHelp`.
                        "selfService": code in rules.SELF_SERVICE,
                        "selfServiceHelp": rules.SELF_SERVICE.get(code),
                    }
                    for code, spec in rules.REQUEST_TYPES.items()
                ],
                "statuses": [{"code": code, "label": label} for code, label in rules.STATUS_LABELS.items()],
            }
        )


@requires_idempotency
class CustomerPortalMessagesView(_PortalView):
    def get(self, request):
        context_type = request.query_params.get("contextType")
        context_ref = request.query_params.get("contextRef")
        if not context_type or not context_ref:
            raise ValidationError({"contextType": "contextType and contextRef are required."})
        return Response(
            {"messages": messages_service.customer_thread(context_type=context_type, context_ref=context_ref)}
        )

    def post(self, request):
        body = MessageSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        message = messages_service.customer_send(
            account_id=_account_id(), context_type=data["contextType"], context_ref=data["contextRef"], body=data["body"]
        )
        return Response(message, status=201)


class CustomerPortalConversationsView(_PortalView):
    def get(self, request):
        return Response({"conversations": messages_service.customer_conversations()})


class CustomerPortalNotificationsView(_PortalView):
    def get(self, request):
        unread_only = request.query_params.get("unread") == "true"
        return Response(notifications_service.list_notifications(_account_id(), unread_only=unread_only))


class CustomerPortalNotificationsReadView(_PortalView):
    def post(self, request):
        body = MarkReadSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = notifications_service.mark_read(_account_id(), ids=body.validated_data["ids"])
        return Response({"updated": updated})


class CustomerPortalRenewalView(_PortalView):
    def get(self, request, policy_number: str):
        return Response(renewal_service.get_renewal(policy_number))


class CustomerPortalPlanCompareView(_PortalView):
    def get(self, request):
        policy_number = request.query_params.get("policyNumber")
        if not policy_number:
            raise ValidationError({"policyNumber": "This query parameter is required."})
        return Response(renewal_service.compare_plans(policy_number))
