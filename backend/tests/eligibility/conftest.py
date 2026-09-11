from __future__ import annotations

import time
import uuid

import jwt
import pytest
from rest_framework.test import APIClient

from apps.foundation.infrastructure.models import Tenant

_SECRET = "eligibility-tests-signing-secret-32b"


@pytest.fixture(autouse=True)
def _oidc_static_key(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = _SECRET
    settings.OIDC_ALGORITHMS = ["HS256"]


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(id=uuid.uuid4(), code=f"tenant-{uuid.uuid4().hex[:8]}", name="Test Tenant")


def make_client(*, tenant_id, roles: list[str], scope: str, actor_id: str = "actor-1") -> APIClient:
    claims = {
        "sub": actor_id,
        "tenant_id": str(tenant_id),
        "roles": roles,
        "scope": scope,
        "exp": int(time.time()) + 300,
    }
    token = jwt.encode(claims, _SECRET, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def admin_client(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
