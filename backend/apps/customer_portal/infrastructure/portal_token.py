"""Self-issued session token for the customer portal.

Deliberately NOT the staff OIDC flow (ROADMAP_PORTAL_CLIENTE.md Fase 0:
"nunca reaproveita os scopes/roles internos"): signed with its own
`CUSTOMER_PORTAL_JWT_SECRET`, never `settings.SECRET_KEY` or an OIDC key,
so a leak/misconfiguration of one can never be used to forge the other.
Short-lived (`CUSTOMER_PORTAL_TOKEN_TTL_SECONDS`) — no refresh-token flow
in Fase 0, matching the roadmap's own phase scoping (a customer
re-authenticates via a fresh OTP once the token expires).
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any

import jwt
from django.conf import settings

ALGORITHM = "HS256"
TOKEN_TYPE = "q360-customer-portal"


class InvalidPortalTokenError(Exception):
    """Raised when a customer-portal bearer token fails to decode/validate."""


class PortalTokenService:
    def issue(
        self, *, tenant_id: uuid.UUID, customer_account_id: uuid.UUID, proposer_ids: list[uuid.UUID]
    ) -> tuple[str, int]:
        ttl_seconds = settings.CUSTOMER_PORTAL_TOKEN_TTL_SECONDS
        now = datetime.datetime.now(datetime.timezone.utc)
        claims = {
            "typ": TOKEN_TYPE,
            "sub": str(customer_account_id),
            "tenant_id": str(tenant_id),
            "proposer_ids": [str(p) for p in proposer_ids],
            "iat": int(now.timestamp()),
            "exp": int((now + datetime.timedelta(seconds=ttl_seconds)).timestamp()),
        }
        token = jwt.encode(claims, settings.CUSTOMER_PORTAL_JWT_SECRET, algorithm=ALGORITHM)
        return token, ttl_seconds

    def decode(self, token: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                key=settings.CUSTOMER_PORTAL_JWT_SECRET,
                algorithms=[ALGORITHM],
                options={"require": ["exp", "sub", "tenant_id"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidPortalTokenError(str(exc)) from exc
        if claims.get("typ") != TOKEN_TYPE:
            raise InvalidPortalTokenError("Token is not a customer-portal token")
        return claims
