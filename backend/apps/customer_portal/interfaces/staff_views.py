"""Lado do backoffice dos pedidos e mensagens do portal (PDF s.8 e 15): quem
atende o cliente. Autenticação normal de staff, sem permissão nova — o
documento funcional (DOC-001 s18) ainda não define uma para isto, e
`permissions.py` proíbe inventá-las; por isso usa os escopos de leitura e
escrita que todos os perfis de trabalho já têm."""
from __future__ import annotations

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application import messages_service, requests_service
from apps.customer_portal.domain import requests as rules
from apps.customer_portal.interfaces.comm_serializers import MessageSerializer, TransitionSerializer
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.foundation.interfaces.permissions import require_scope


def _actor_ref(request) -> str:
    actor = getattr(getattr(request, "user", None), "actor", None)
    return actor.actor_id if actor else "unknown"


class PortalRequestListView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        status = request.query_params.get("status")
        request_type = request.query_params.get("type")
        if status and status not in rules.STATUS_LABELS:
            raise ValidationError({"status": f"Must be one of {sorted(rules.STATUS_LABELS)}."})
        if request_type and request_type not in rules.REQUEST_TYPES:
            raise ValidationError({"type": f"Must be one of {sorted(rules.REQUEST_TYPES)}."})
        return Response({"requests": requests_service.staff_list(status=status, request_type=request_type)})


class PortalRequestDetailView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, request_number: str):
        return Response(requests_service.staff_get(request_number))


@requires_idempotency
class PortalRequestTransitionView(APIView):
    permission_classes = [require_scope(Scope.WRITE)]

    def post(self, request, request_number: str):
        body = TransitionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(
            requests_service.staff_transition(
                request_number=request_number, to_status=data["toStatus"], note=data["note"], actor_ref=_actor_ref(request)
            )
        )


class PortalConversationListView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        return Response(
            {"conversations": messages_service.staff_inbox(unread_only=request.query_params.get("unread") == "true")}
        )


@requires_idempotency
class PortalStaffMessagesView(APIView):
    def get_permissions(self):
        return [require_scope(Scope.WRITE if self.request.method == "POST" else Scope.READ)()]

    def get(self, request):
        context_type = request.query_params.get("contextType")
        context_ref = request.query_params.get("contextRef")
        if not context_type or not context_ref:
            raise ValidationError({"contextType": "contextType and contextRef are required."})
        return Response(
            {"messages": messages_service.staff_thread(context_type=context_type, context_ref=context_ref)}
        )

    def post(self, request):
        body = MessageSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        message = messages_service.staff_send(
            context_type=data["contextType"], context_ref=data["contextRef"], body=data["body"],
            actor_ref=_actor_ref(request),
        )
        return Response(message, status=201)
