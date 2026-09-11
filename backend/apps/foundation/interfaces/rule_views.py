"""ART-006 `/api/v1/rule-versions`: `createRuleVersion` (POST), security ->
oauth2: [q360.admin]. No DOC-001 s18 permission exists for rule
configuration specifically; gated by scope alone (same reasoning as the
client module — see docs/08-integration-contract/BACKEND_FRONTEND_ALIGNMENT.md).
"""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application.rule_service import create_rule_version
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope
from apps.foundation.interfaces.rule_serializers import (
    RuleSetVersionRequestSerializer,
    VersionedConfigHeaderSerializer,
)


class RuleVersionCreateView(APIView):
    permission_classes = [require_scope(Scope.ADMIN)]

    def post(self, request):
        body = RuleSetVersionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        rule_version = create_rule_version(**body.validated_data)
        return Response(VersionedConfigHeaderSerializer(rule_version).data, status=201)
