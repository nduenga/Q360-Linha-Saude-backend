"""Self-issued staff access token.

Signed with `Q360_JWT_SIGNING_KEY` (HS256) - a distinct, production-legit
setting from `OIDC_STATIC_VERIFICATION_KEY` (that one stays a dev/test-only
escape hatch, still blocked in production by config/settings/production.py).
Symmetric, not RS256/JWKS: the issuer (this module) and the validator
(`apps.foundation.infrastructure.jwt_actor_adapter.JwtActorAdapter`) are the
same Django process, so there is no separate-service key-distribution
problem an asymmetric key would solve - same reasoning already applied to
`apps.customer_portal.infrastructure.portal_token.PortalTokenService`.

Critically, `JwtActorAdapter` itself is untouched: it already reads
`settings.OIDC_TENANT_CLAIM`/`OIDC_ROLES_CLAIM`/`OIDC_SCOPE_CLAIM` claim
*names* from config rather than hardcoding them, so this module just has to
emit a token shaped the same way `DevLoginView`
(apps.foundation.interfaces.auth_views) already does - the resource-server
side needs zero changes to accept a staff-issued token instead of an
Auth0-issued one.
"""
from __future__ import annotations

import datetime
import uuid

import jwt
from django.conf import settings

ALGORITHM = "HS256"


class StaffSigningKeyMissingError(Exception):
    """Raised if Q360_JWT_SIGNING_KEY is unset - never silently falls back
    to SECRET_KEY or the dev-only OIDC_STATIC_VERIFICATION_KEY."""


def issue_access_token(*, actor_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str], scopes: list[str]) -> tuple[str, int]:
    if not settings.Q360_JWT_SIGNING_KEY:
        raise StaffSigningKeyMissingError("A chave Q360_JWT_SIGNING_KEY não está configurada")

    ttl_seconds = settings.Q360_STAFF_ACCESS_TOKEN_TTL_SECONDS
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "sub": str(actor_id),
        settings.OIDC_TENANT_CLAIM: str(tenant_id),
        settings.OIDC_ROLES_CLAIM: roles,
        settings.OIDC_SCOPE_CLAIM: " ".join(scopes),
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=ttl_seconds)).timestamp()),
    }
    token = jwt.encode(claims, settings.Q360_JWT_SIGNING_KEY, algorithm=ALGORITHM)
    return token, ttl_seconds
