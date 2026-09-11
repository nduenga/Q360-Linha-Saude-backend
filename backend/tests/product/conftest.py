from __future__ import annotations

import time
import uuid

import jwt
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.foundation.infrastructure.models import Tenant

_SECRET = "product-tests-signing-secret-32-bytes-min"


@pytest.fixture(autouse=True)
def _oidc_static_key(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = _SECRET
    settings.OIDC_ALGORITHMS = ["HS256"]


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(id=uuid.uuid4(), code=f"tenant-{uuid.uuid4().hex[:8]}", name="Test Tenant")


def _token(*, tenant_id, roles: list[str], scope: str, actor_id: str = "actor-1") -> str:
    claims = {
        "sub": actor_id,
        "tenant_id": str(tenant_id),
        "roles": roles,
        "scope": scope,
        "exp": int(time.time()) + 300,
    }
    return jwt.encode(claims, _SECRET, algorithm="HS256")


def make_client(*, tenant_id, roles: list[str], scope: str, actor_id: str = "actor-1") -> APIClient:
    client = APIClient()
    token = _token(tenant_id=tenant_id, roles=roles, scope=scope, actor_id=actor_id)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def admin_client(tenant):
    # ADMIN role covers product:manage + pricing-config:manage (DOC-001
    # s18); q360.admin scope covers every operation used in these tests.
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
