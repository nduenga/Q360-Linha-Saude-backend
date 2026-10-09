"""JwtActorAdapter tests using the dev-only HS256 static-key escape hatch
(OIDC_STATIC_VERIFICATION_KEY) — no JWKS endpoint required. See
OPEN_DECISIONS.md#S01-AUTH-001.
"""
from __future__ import annotations

import time

import jwt
import pytest
from django.test import override_settings

from apps.foundation.infrastructure.jwt_actor_adapter import InvalidTokenError, JwtActorAdapter

_SECRET = "test-signing-secret-at-least-32-bytes-long"
_TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _sign(claims: dict) -> str:
    return jwt.encode(claims, _SECRET, algorithm="HS256")


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_maps_valid_token_to_actor():
    token = _sign(
        {
            "sub": "user-1",
            "tenant_id": _TENANT_ID,
            "roles": ["SUBSCRIBER", "SUBSCRIPTION_MANAGER"],
            "exp": int(time.time()) + 300,
        }
    )
    actor = JwtActorAdapter().resolve(token)
    assert actor.actor_id == "user-1"
    assert str(actor.tenant_id) == _TENANT_ID
    assert {r.value for r in actor.roles} == {"SUBSCRIBER", "SUBSCRIPTION_MANAGER"}


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_ignores_unknown_role_claim():
    token = _sign(
        {
            "sub": "user-1",
            "tenant_id": _TENANT_ID,
            "roles": ["SUBSCRIBER", "SOMETHING_NOT_IN_DOC001"],
            "exp": int(time.time()) + 300,
        }
    )
    actor = JwtActorAdapter().resolve(token)
    assert {r.value for r in actor.roles} == {"SUBSCRIBER"}


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_rejects_missing_tenant_claim():
    token = _sign({"sub": "user-1", "exp": int(time.time()) + 300})
    with pytest.raises(InvalidTokenError, match="tenant_id"):
        JwtActorAdapter().resolve(token)


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_rejects_expired_token():
    token = _sign(
        {"sub": "user-1", "tenant_id": _TENANT_ID, "exp": int(time.time()) - 10}
    )
    with pytest.raises(InvalidTokenError):
        JwtActorAdapter().resolve(token)


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_rejects_bad_signature():
    token = jwt.encode(
        {"sub": "user-1", "tenant_id": _TENANT_ID, "exp": int(time.time()) + 300},
        "wrong-secret-but-still-32-bytes-long",
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        JwtActorAdapter().resolve(token)


@override_settings(OIDC_STATIC_VERIFICATION_KEY="", OIDC_JWKS_URL="")
def test_resolve_fails_closed_when_unconfigured():
    token = _sign({"sub": "user-1", "tenant_id": _TENANT_ID, "exp": int(time.time()) + 300})
    with pytest.raises(InvalidTokenError, match="Nenhuma de OIDC_JWKS_URL"):
        JwtActorAdapter().resolve(token)


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_parses_space_delimited_scope_claim():
    # RFC 8693 standard shape: a single space-delimited string.
    token = _sign(
        {
            "sub": "user-1",
            "tenant_id": _TENANT_ID,
            "scope": "q360.read q360.write",
            "exp": int(time.time()) + 300,
        }
    )
    actor = JwtActorAdapter().resolve(token)
    assert {s.value for s in actor.scopes} == {"q360.read", "q360.write"}


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_ignores_unknown_scope_claim():
    token = _sign(
        {
            "sub": "user-1",
            "tenant_id": _TENANT_ID,
            "scope": "q360.read not-a-real-scope",
            "exp": int(time.time()) + 300,
        }
    )
    actor = JwtActorAdapter().resolve(token)
    assert {s.value for s in actor.scopes} == {"q360.read"}


@override_settings(OIDC_STATIC_VERIFICATION_KEY=_SECRET, OIDC_ALGORITHMS=["HS256"])
def test_resolve_defaults_to_no_scopes_when_claim_absent():
    token = _sign({"sub": "user-1", "tenant_id": _TENANT_ID, "exp": int(time.time()) + 300})
    actor = JwtActorAdapter().resolve(token)
    assert actor.scopes == frozenset()
