from __future__ import annotations

import datetime
import time
import uuid

import jwt
import pytest
from rest_framework.test import APIClient

from apps.foundation.infrastructure.models import Tenant

_SECRET = "quote-tests-signing-secret-32-bytes"


@pytest.fixture(autouse=True)
def _oidc_static_key(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = _SECRET
    settings.OIDC_ALGORITHMS = ["HS256"]


def set_quote_created_on(quote_id, day: datetime.date) -> None:
    """A cotação não tem data de efeito (2026-10-15): a data de referência do
    cálculo (idades, configurações em vigor) é o dia de criação. Os casos de
    referência do Excel fixam-no no dia de referência do livro."""
    from apps.quote.infrastructure.models import Quote

    moment = datetime.datetime.combine(day, datetime.time(12), tzinfo=datetime.timezone.utc)
    Quote.all_tenants.filter(id=quote_id).update(created_at=moment)


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
    # ADMIN also carries q360.approve here (unlike other modules' fixtures)
    # because Sprint 7's own tests need a single actor able to exercise
    # every scope up to the point where segregation-of-duties or a missing
    # DOC-001 permission is the thing actually being tested.
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin q360.approve")
