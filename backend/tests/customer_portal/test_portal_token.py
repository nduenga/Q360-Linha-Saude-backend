"""apps.customer_portal.infrastructure.portal_token — no DB, just the
JWT issue/decode roundtrip and its isolation from the staff OIDC secret
(ROADMAP_PORTAL_CLIENTE.md Fase 0: "nunca reaproveita os scopes/roles
internos").
"""
from __future__ import annotations

import uuid

import jwt
import pytest
from django.conf import settings

from apps.customer_portal.infrastructure.portal_token import InvalidPortalTokenError, PortalTokenService


def test_issue_and_decode_roundtrip():
    tokens = PortalTokenService()
    tenant_id = uuid.uuid4()
    customer_account_id = uuid.uuid4()
    proposer_id = uuid.uuid4()

    token, ttl_seconds = tokens.issue(
        tenant_id=tenant_id, customer_account_id=customer_account_id, proposer_ids=[proposer_id]
    )
    assert ttl_seconds == settings.CUSTOMER_PORTAL_TOKEN_TTL_SECONDS

    claims = tokens.decode(token)
    assert claims["sub"] == str(customer_account_id)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["proposer_ids"] == [str(proposer_id)]


def test_decode_rejects_a_staff_style_token_signed_with_a_different_secret():
    tokens = PortalTokenService()
    forged = jwt.encode(
        {"typ": "q360-customer-portal", "sub": "x", "tenant_id": str(uuid.uuid4())},
        "some-other-secret",
        algorithm="HS256",
    )
    with pytest.raises(InvalidPortalTokenError):
        tokens.decode(forged)


def test_decode_rejects_a_token_without_the_portal_type_marker():
    forged = jwt.encode(
        {"sub": "x", "tenant_id": str(uuid.uuid4()), "exp": 9999999999},
        settings.CUSTOMER_PORTAL_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidPortalTokenError):
        PortalTokenService().decode(forged)
