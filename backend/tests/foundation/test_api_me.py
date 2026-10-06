"""GET /api/v1/me (Q360-S1-03, ART-006 operationId getCurrentActor) — no DB
access, so no @pytest.mark.django_db needed: the actor is resolved entirely
from JWT claims.

Response shape asserted here is ART-006's `ActorContext` schema verbatim
(camelCase field names); error shape is ART-006's `ProblemDetail` +
x-q360-error-catalog codes — not a locally invented envelope.
"""
from __future__ import annotations

import json
import time

import jwt
from django.test import override_settings
from rest_framework.test import APIClient

_SECRET = "test-signing-secret-at-least-32-bytes-long"
_TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _sign(**extra_claims) -> str:
    claims = {
        "sub": "user-1",
        "tenant_id": _TENANT_ID,
        "roles": ["SUBSCRIPTION_MANAGER"],
        "scope": "q360.read",
        "exp": int(time.time()) + 300,
    }
    claims.update(extra_claims)
    return jwt.encode(claims, _SECRET, algorithm="HS256")


def test_me_requires_authentication():
    response = APIClient().get("/api/v1/me")
    assert response.status_code == 401
    assert response["Content-Type"] == "application/problem+json"
    assert response.data["code"] == "AUTH-401"
    assert response.data["status"] == 401
    # Body correlationId must be the same value CorrelationIdMiddleware
    # echoed on the X-Correlation-Id response header, not an independent
    # or empty value.
    assert response.data["correlationId"] == response["X-Correlation-Id"]
    assert response.data["correlationId"]
    # `response.data` is DRF's pre-render dict; also assert the actual HTTP
    # body bytes are well-formed JSON with a correct UTF-8 title, since a
    # forced `content_type` on Response bypasses the usual renderer checks.
    body = json.loads(response.content)
    assert body["title"] == "Não autenticado"


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_me_rejects_invalid_token():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.data["code"] == "AUTH-401"


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_me_requires_read_scope():
    # ART-006 security block for GET /api/v1/me: oauth2 -> [q360.read].
    # A token with roles/permissions but no matching OAuth2 scope must be
    # rejected, independently of the DOC-001 RBAC layer.
    token = _sign(scope="q360.write")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.get("/api/v1/me")
    assert response.status_code == 403
    assert response.data["code"] == "AUTH-403"


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_me_returns_actor_context_schema():
    token = _sign()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.get("/api/v1/me")

    assert response.status_code == 200
    assert set(response.data.keys()) == {"actorId", "tenantId", "roles", "permissions"}
    assert response.data["actorId"] == "user-1"
    assert response.data["tenantId"] == _TENANT_ID
    assert response.data["roles"] == ["SUBSCRIPTION_MANAGER"]
    assert "audit:read" in response.data["permissions"]
    assert "quote:approve" in response.data["permissions"]
