"""Lado do backoffice dos pedidos e mensagens do portal (PDF s.8 e 15): quem
atende o cliente. Autenticação normal de staff, sem permissão nova — o
documento funcional (DOC-001 s18) ainda não define uma para isto, e
`permissions.py` proíbe inventá-las; por isso usa os escopos de leitura e
escrita que todos os perfis de trabalho já têm."""
from __future__ import annotations

from django.db.models import Avg, Count
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema

from apps.customer_portal.application import messages_service, requests_service
from apps.customer_portal.domain import requests as rules
from apps.customer_portal.infrastructure.models import PortalRequestSatisfaction
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


class PortalRequestMetricsView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    @extend_schema(parameters=[
        OpenApiParameter("status", str, description="Filtra as métricas temporais pelo estado do pedido."),
        OpenApiParameter("type", str, description="Filtra as métricas temporais pelo tipo do pedido."),
    ])
    def get(self, request):
        from apps.business_config.application.readers import BusinessSnapshot

        config = BusinessSnapshot.load().get("service.satisfaction") or {}
        stats = PortalRequestSatisfaction.objects.aggregate(count=Count("id"), average=Avg("score"))
        distribution = list(
            PortalRequestSatisfaction.objects.values("score").annotate(count=Count("id")).order_by("score")
        )
        # Use the same per-request SLA clock and pause rules as the queue so
        # aggregate durations cannot silently mix business and elapsed time.
        status_filter = request.query_params.get("status")
        type_filter = request.query_params.get("type")
        if status_filter and status_filter not in rules.STATUS_LABELS:
            raise ValidationError({"status": f"Must be one of {sorted(rules.STATUS_LABELS)}."})
        if type_filter and type_filter not in rules.REQUEST_TYPES:
            raise ValidationError({"type": f"Must be one of {sorted(rules.REQUEST_TYPES)}."})
        rows = requests_service.staff_list(status=status_filter, request_type=type_filter)
        service_groups = {}
        for row in rows:
            sla = row.get("sla")
            if not sla or sla.get("measurementStatus") != "MEASURED":
                continue
            key = (sla.get("clock"), sla.get("priority"))
            group = service_groups.setdefault(key, {
                "clock": key[0], "priority": key[1], "requests": 0,
                "firstResponseTotal": 0, "firstResponseCount": 0,
                "resolutionTotal": 0, "resolutionCount": 0,
            })
            group["requests"] += 1
            for field, total_key, count_key in (
                ("firstResponseMinutes", "firstResponseTotal", "firstResponseCount"),
                ("resolutionMinutes", "resolutionTotal", "resolutionCount"),
            ):
                value = sla.get(field)
                if value is not None:
                    group[total_key] += value
                    group[count_key] += 1
        service_time = []
        for group in sorted(service_groups.values(), key=lambda item: (item["clock"], item["priority"])):
            service_time.append({
                "clock": group["clock"], "priority": group["priority"],
                "measuredRequests": group["requests"],
                "firstResponse": {
                    "measuredRequests": group["firstResponseCount"],
                    "averageMinutes": round(group["firstResponseTotal"] / group["firstResponseCount"], 2)
                    if group["firstResponseCount"] else None,
                },
                "resolution": {
                    "measuredRequests": group["resolutionCount"],
                    "averageMinutes": round(group["resolutionTotal"] / group["resolutionCount"], 2)
                    if group["resolutionCount"] else None,
                },
            })
        return Response({
            "satisfaction": {
                "enabled": bool(config.get("enabled")),
                "responses": stats["count"],
                "averageScore": round(stats["average"], 2) if stats["average"] is not None else None,
                "minimumScore": config.get("minimum_score"),
                "maximumScore": config.get("maximum_score"),
                "distribution": distribution,
            },
            "serviceTime": {
                "definition": "Médias calculadas com os mesmos relógios SLA dos pedidos; pedidos não medidos são excluídos.",
                "items": service_time,
            },
        })


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
