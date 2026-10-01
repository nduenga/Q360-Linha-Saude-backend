"""`/api/v1/system-parameters` — parâmetros globais do sistema (R7)."""
from __future__ import annotations

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application import system_parameter_service as service
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope


class SystemParameterUpdateSerializer(serializers.Serializer):
    value = serializers.JSONField()
    rowVersion = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class SystemParameterRollbackSerializer(serializers.Serializer):
    revisionNo = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class SystemParameterRevisionSerializer(serializers.Serializer):
    revisionNo = serializers.IntegerField(source="revision_no")
    action = serializers.CharField()
    value = serializers.JSONField(source="value_json")
    reason = serializers.CharField(allow_null=True)
    changedBy = serializers.CharField(source="changed_by")
    createdAt = serializers.DateTimeField(source="created_at")


class SystemParameterListView(APIView):
    """GET lists every parameter with its current value, default, whether the
    GTE may change it (OPERATIONAL) or not (STRUCTURAL) and where it is used.
    Filter: `?category=OPERATIONAL|STRUCTURAL`."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        return Response(service.list_parameters(category=request.query_params.get("category")))


@requires_idempotency
class SystemParameterDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "PUT":
            return [require_scope(Scope.ADMIN)(), require_permission(Permission.PRICING_CONFIG_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, code):
        return Response(service.describe(code))

    def put(self, request, code):
        body = SystemParameterUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(
            service.set_value(code=code, value=data["value"], reason=data["reason"], row_version=data["rowVersion"])
        )


class SystemParameterRevisionsView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, code):
        return Response(SystemParameterRevisionSerializer(service.list_revisions(code=code), many=True).data)


@requires_idempotency
class SystemParameterRollbackView(APIView):
    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]

    def post(self, request, code):
        body = SystemParameterRollbackSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(service.rollback(code=code, revision_no=body.validated_data["revisionNo"], reason=body.validated_data["reason"]))
