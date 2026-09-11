"""JwtActorAdapter (DOC-004 s6.1) — OAuth2/OIDC Resource Server JWT validation.

Validates signature, issuer, audience and expiry against the configured
Identity Provider (via JWKS), then maps claims to an `Actor`.

OPEN DECISION — do not harden assumptions here:
DOC-001 s"Identity Provider" says only "autenticação/claims conforme
ambiente", and DOC-004's Open Decisions list OD-009 "OIDC provider/claims"
as unresolved. No approved Q360 document fixes the concrete IdP or the
exact claim names for tenant/roles/scope. This adapter is therefore
configuration-driven (Q360_OIDC_* env vars / settings.OIDC_*) instead of
hardcoded to one vendor's claim shape. See backend/OPEN_DECISIONS.md
(S01-AUTH-001) — resolve there, not by editing claim names in this file.

Note: the OAuth2 *scope values* (q360.read/write/approve/admin/audit) ARE
fixed by ART-006 `components.securitySchemes.oauth2` — only the JWT claim
name carrying them (OIDC_SCOPE_CLAIM) is open, same as tenant/roles.
"""
from __future__ import annotations

import logging
from typing import Any

import jwt
from django.conf import settings

from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId

logger = logging.getLogger(__name__)


class InvalidTokenError(Exception):
    """Raised when a bearer token fails signature, claim or expiry validation."""


class JwtActorAdapter:
    def __init__(self) -> None:
        self._jwks_client: jwt.PyJWKClient | None = None
        if settings.OIDC_JWKS_URL:
            self._jwks_client = jwt.PyJWKClient(settings.OIDC_JWKS_URL)

    def resolve(self, bearer_token: str) -> Actor:
        try:
            claims = self._decode(bearer_token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        subject = claims.get("sub")
        if not subject:
            raise InvalidTokenError("Token is missing required claim 'sub'")

        tenant_claim = settings.OIDC_TENANT_CLAIM
        raw_tenant_id = claims.get(tenant_claim)
        if not raw_tenant_id:
            raise InvalidTokenError(f"Token is missing required claim '{tenant_claim}'")
        try:
            tenant_id = TenantId.parse(raw_tenant_id)
        except (ValueError, AttributeError) as exc:
            raise InvalidTokenError(
                f"Claim '{tenant_claim}' is not a valid tenant identifier"
            ) from exc

        roles = _parse_roles(claims.get(settings.OIDC_ROLES_CLAIM, []))
        scopes = _parse_scopes(claims.get(settings.OIDC_SCOPE_CLAIM, ""))

        return Actor(
            actor_id=str(subject),
            tenant_id=tenant_id,
            roles=roles,
            scopes=scopes,
            actor_type="USER",
        )

    def _decode(self, bearer_token: str) -> dict[str, Any]:
        if self._jwks_client is not None:
            signing_key = self._jwks_client.get_signing_key_from_jwt(bearer_token).key
        elif settings.OIDC_STATIC_VERIFICATION_KEY:
            # Local/dev-only escape hatch for environments without a running
            # OIDC provider. Never set in production (enforced in
            # config/settings/production.py).
            signing_key = settings.OIDC_STATIC_VERIFICATION_KEY
        else:
            raise InvalidTokenError(
                "No OIDC_JWKS_URL or OIDC_STATIC_VERIFICATION_KEY configured"
            )

        return jwt.decode(
            bearer_token,
            key=signing_key,
            algorithms=settings.OIDC_ALGORITHMS,
            audience=settings.OIDC_AUDIENCE or None,
            issuer=settings.OIDC_ISSUER or None,
            options={"require": ["exp", "sub"]},
        )


def _parse_roles(raw_roles: Any) -> frozenset[Role]:
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles: set[Role] = set()
    for raw in raw_roles or []:
        try:
            roles.add(Role(str(raw).upper()))
        except ValueError:
            logger.warning("Ignoring unknown role claim value: %r", raw)
    return frozenset(roles)


def _parse_scopes(raw_scope: Any) -> frozenset[Scope]:
    # RFC 8693 / standard OAuth2 convention: a single space-delimited
    # string. Some providers emit a list instead; accept both.
    if isinstance(raw_scope, str):
        raw_values = raw_scope.split()
    else:
        raw_values = list(raw_scope or [])
    scopes: set[Scope] = set()
    for raw in raw_values:
        try:
            scopes.add(Scope(str(raw)))
        except ValueError:
            logger.warning("Ignoring unknown scope claim value: %r", raw)
    return frozenset(scopes)
