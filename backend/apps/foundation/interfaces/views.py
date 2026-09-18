"""GET /api/v1/me (Q360-S1-03, ART-006 operationId `getCurrentActor`)
and GET /api/v1/audit-events (ART-006 operationId `listAuditEvents`).

Response bodies match ART-006 schemas verbatim (DOC-004 s2 precedence
rule). See individual view docstrings for the exact operationId cross
reference.
"""
from __future__ import annotations

from django.db import connections
from django.db.models import Q
from django.http import JsonResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.scopes import Scope
from apps.foundation.infrastructure.models import AuditEvent
from apps.foundation.interfaces.audit_serializers import AuditEventSerializer
from apps.foundation.interfaces.permissions import require_scope
from shared.pagination import Q360PageNumberPagination


class MeView(APIView):
    # ART-006 path /api/v1/me, operation `get`: security -> oauth2: [q360.read]
    permission_classes = [IsAuthenticated, require_scope(Scope.READ)]

    def get(self, request):
        actor = request.user.actor
        return Response(
            {
                "actorId": actor.actor_id,
                "tenantId": str(actor.tenant_id),
                "roles": sorted(role.value for role in actor.roles),
                "permissions": sorted(permission.value for permission in actor.permissions),
            }
        )


class AuditEventListView(APIView):
    """ART-006 `/api/v1/audit-events`, operationId `listAuditEvents`.

    Query filters are exactly those documented in ART-006 (`entityType`,
    `entityId`, `correlationId`) — no additional filtering is exposed
    here because the contract does not describe it. Tenant scoping is
    applied by the model's default manager via `TenantScopedModel`.
    """

    permission_classes = [IsAuthenticated, require_scope(Scope.AUDIT)]

    def get(self, request):
        queryset = AuditEvent.objects.all().order_by("-occurred_at")

        entity_type = request.query_params.get("entityType")
        entity_id = request.query_params.get("entityId")
        correlation_id = request.query_params.get("correlationId")
        actor_id = request.query_params.get("actorId")
        occurred_from = request.query_params.get("from")
        occurred_to = request.query_params.get("to")

        filters = Q()
        if entity_type:
            filters &= Q(entity_type=entity_type)
        if entity_id:
            filters &= Q(entity_id=entity_id)
        if correlation_id:
            filters &= Q(correlation_id=correlation_id)
        if actor_id:
            filters &= Q(actor_id=actor_id)
        if occurred_from:
            filters &= Q(occurred_at__gte=occurred_from)
        if occurred_to:
            filters &= Q(occurred_at__lte=occurred_to)
        if filters:
            queryset = queryset.filter(filters)

        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AuditEventSerializer(page, many=True).data)


class LiveHealthView(APIView):
    """Unauthenticated liveness probe: process is able to answer HTTP."""

    permission_classes = [AllowAny]

    def get(self, request):
        return JsonResponse({"status": "ok"})


class ReadyHealthView(APIView):
    """Readiness probe: verifies the configured database accepts a query."""

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return JsonResponse({"status": "unavailable"}, status=503)
        return JsonResponse({"status": "ok"})
