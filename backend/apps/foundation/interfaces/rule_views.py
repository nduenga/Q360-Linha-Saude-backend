"""ART-006 `/api/v1/rule-versions`: `createRuleVersion` (POST), security ->
oauth2: [q360.admin]. No DOC-001 s18 permission exists for rule
configuration specifically; gated by scope alone (same reasoning as the
client module — see docs/08-integration-contract/BACKEND_FRONTEND_ALIGNMENT.md).
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application.rule_service import create_rule_version, delete_rule_version, update_rule_version
from apps.foundation.domain.scopes import Scope
from apps.foundation.infrastructure.models import RuleVersion
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.foundation.interfaces.permissions import require_scope
from apps.foundation.interfaces.rule_serializers import (
    RuleSetVersionRequestSerializer,
    RuleVersionUpdateRequestSerializer,
    VersionedConfigHeaderSerializer,
)
from shared.pagination import Q360PageNumberPagination


@requires_idempotency
class RuleVersionCreateView(APIView):
    """`GET` (list, optional `?ruleDomain=`) is a pragmatic V1 addition,
    not in ART-006 — see OPEN_DECISIONS.md#S04-LISTING-GAPS-001/DECISIONS_TAKEN.md."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.ADMIN)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        queryset = RuleVersion.objects.select_related("rule_set").order_by(
            "rule_set__code", "-version_no"
        )
        rule_domain = request.query_params.get("ruleDomain")
        if rule_domain:
            queryset = queryset.filter(rule_set__rule_domain=rule_domain)
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(VersionedConfigHeaderSerializer(page, many=True).data)

    def post(self, request):
        body = RuleSetVersionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        rule_version = create_rule_version(**body.validated_data)
        return Response(VersionedConfigHeaderSerializer(rule_version).data, status=201)


@requires_idempotency
class RuleVersionDetailView(APIView):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6, pragmatic V1 addition, not
    in ART-006. `PATCH`/`DELETE` only work while `status=DRAFT`."""

    permission_classes = [require_scope(Scope.ADMIN)]

    def patch(self, request, rule_version_id):
        rule_version = get_object_or_404(RuleVersion.objects.select_related("rule_set"), id=rule_version_id)
        body = RuleVersionUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = update_rule_version(
            rule_version,
            name=data["name"],
            artifact_type=data["artifact_type"],
            artifact_ref=data["artifact_ref"],
            artifact_checksum=data["artifact_checksum"],
        )
        return Response(VersionedConfigHeaderSerializer(updated).data)

    def delete(self, request, rule_version_id):
        rule_version = get_object_or_404(RuleVersion, id=rule_version_id)
        delete_rule_version(rule_version)
        return Response(status=204)
