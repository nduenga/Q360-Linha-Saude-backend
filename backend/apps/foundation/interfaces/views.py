"""GET /api/v1/me (Q360-S1-03, ART-006 operationId `getCurrentActor`).

Response body is ART-006's `ActorContext` schema verbatim — field names are
camelCase and the set is closed (`additionalProperties: false`): `actorId`,
`tenantId`, `roles`, `permissions`. Do not rename or add fields without
updating ART-006 first (DOC-004 s2 precedence rule).

There is no local user table in V1 (ART-005 has none) — this reflects JWT
claims, not a stored profile.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope


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
