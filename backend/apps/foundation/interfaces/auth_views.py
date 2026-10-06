"""Pragmatic dev/demo login bridge — `POST /api/v1/auth/dev-login`.

NOT in ART-006 (documented as a pragmatic V1 addition, same posture as
every other "not in ART-006" endpoint in this codebase — see
DECISIONS_TAKEN.md). NOT the resolution of OD-009 (real OIDC/IdP
integration): a real IdP would replace the frontend's whole login screen
with a redirect-based Authorization Code flow, never a direct POST of a
password to this backend. This exists only so the frontend's *existing*
login UI (`Q360-Linha-Sa-de-frontend/src/auth/LoginPage.tsx`, previously
100% client-side mocked) can obtain a real, backend-issued JWT and call
every already-built endpoint as a real authenticated actor.

Uses the exact same `OIDC_STATIC_VERIFICATION_KEY` escape hatch as
`manage.py issue_dev_token` (apps/foundation/management/commands/) — this
view is that same mechanism reachable over HTTP instead of the CLI, kept
in sync deliberately. `config/settings/production.py` refuses to start at
all when this key is set, so this endpoint is structurally a 404 in
production (returned before any credential is even checked).

The two demo identities mirror exactly what the frontend already had
hardcoded in `src/auth/services/mockAuth.ts` (admin@q360.co.ao /
subscritor@q360.co.ao) — the intent is to make the *existing* login form
real, not to introduce new test users. Their roles/scopes are resolved
against the real DOC-001 §18 matrix (`apps.foundation.domain.permissions`)
rather than duplicating that matrix in this file, so `GET /api/v1/me`
called right after login always reflects the one source of truth.
"""
from __future__ import annotations

import time

import jwt
from django.conf import settings
from django.http import Http404
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Role
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.interfaces.auth_serializers import (
    DevLoginRequestSerializer,
    DevLoginResponseSerializer,
)

_DEV_TENANT_CODE = "dev-tenant"
_TTL_SECONDS = 3600

# The first two identities are what the frontend's mockAuth.ts already
# advertised on the login screen — real roles now, not a hardcoded
# permission array. `aprovador@q360.co.ao` is a pragmatic V1 addition:
# ART-012's `ck_decision_four_eyes` requires a *different actor* to decide
# a quote than the one who submitted it, so testing the review workflow
# end-to-end through the UI (not just curl + issue_dev_token) needs a
# second login-able identity with Role.SUBSCRIPTION_MANAGER, distinct from admin-demo.
_DEV_USERS = {
    "admin@q360.co.ao": {
        "password": "Q360admin2026",
        "actor_id": "admin-demo",
        "name": "Administrador Q360",
        "roles": [Role.ADMIN],
        "scopes": "q360.read q360.write q360.admin q360.approve q360.audit",
    },
    "aprovador@q360.co.ao": {
        "password": "Q360aprova2026",
        "actor_id": "aprovador-demo",
        "name": "Gestor de Subscrição Q360",
        "roles": [Role.SUBSCRIPTION_MANAGER],
        "scopes": "q360.read q360.write q360.admin q360.approve q360.audit",
    },
    "subscritor@q360.co.ao": {
        "password": "Q360demo2026",
        "actor_id": "subscritor-demo",
        "name": "Madalena José",
        "roles": [Role.SUBSCRIBER],
        "scopes": "q360.read q360.write q360.approve",
    },
}


class DevLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.OIDC_STATIC_VERIFICATION_KEY:
            # Mirrors issue_dev_token's CommandError guard: structurally
            # absent wherever the static-key escape hatch is absent
            # (always true in production).
            raise Http404

        body = DevLoginRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        email = body.validated_data["email"].strip().lower()
        password = body.validated_data["password"]

        user = _DEV_USERS.get(email)
        if user is None or user["password"] != password:
            raise AuthenticationFailed("Invalid email or password.")

        tenant, _ = Tenant.objects.get_or_create(
            code=_DEV_TENANT_CODE, defaults={"name": "Dev Tenant"}
        )
        claims = {
            "sub": user["actor_id"],
            settings.OIDC_TENANT_CLAIM: str(tenant.id),
            settings.OIDC_ROLES_CLAIM: [role.value for role in user["roles"]],
            settings.OIDC_SCOPE_CLAIM: user["scopes"],
            "exp": int(time.time()) + _TTL_SECONDS,
        }
        token = jwt.encode(claims, settings.OIDC_STATIC_VERIFICATION_KEY, algorithm="HS256")

        payload = {"accessToken": token, "expiresIn": _TTL_SECONDS, "name": user["name"]}
        return Response(DevLoginResponseSerializer(payload).data)
