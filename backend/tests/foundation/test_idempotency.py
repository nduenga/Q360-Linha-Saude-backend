"""Q360-S9-03 Idempotência acceptance criteria (AC-3 in
.trae/specs/s09-s11-restantes/spec.md): same (key, tenant, operation, body)
replays the recorded response without re-executing the view; same key with
a different body is rejected with 409 IDEMP-REPLAY; a required key that is
missing is rejected with 400 VALIDATION-400.

`POST /api/v1/products` is used as the exercised endpoint — it is
`@requires_idempotency`-decorated (apps/product/interfaces/views.py) and
needs no other setup, keeping the test focused on the middleware/service
contract rather than product domain rules.
"""
from __future__ import annotations

import uuid

import pytest

from tests.foundation.conftest import make_client


@pytest.fixture(autouse=True)
def _idempotency_required(settings):
    settings.IDEMPOTENCY_REQUIRED = True


@pytest.mark.django_db
def test_same_key_same_body_is_replayed(admin_client):
    key = str(uuid.uuid4())
    code = f"IDEMP-{uuid.uuid4().hex[:8]}"
    body = {"code": code, "name": "Idempotent Product"}

    first = admin_client.post("/api/v1/products", body, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert first.status_code == 201
    second = admin_client.post("/api/v1/products", body, format="json", HTTP_IDEMPOTENCY_KEY=key)

    assert second.status_code == first.status_code
    assert second.json() == first.json()

    from apps.product.infrastructure.models import Product

    assert Product.objects.filter(code=code).count() == 1


@pytest.mark.django_db
def test_same_key_different_body_returns_409_idemp_replay(admin_client):
    """KNOWN ISSUE (see DECISIONS_TAKEN.md#S09-IDEMPOTENCY-001): passes in
    isolation but has been observed to fail intermittently when run after
    another test in the same session — the second `admin_client.post()`
    call's `IdempotencyRecord.all_tenants.create()` occasionally raises a
    foreign-key violation claiming the *same* tenant used by the first
    call moments earlier "is not present in table tenant", instead of the
    expected unique-constraint IntegrityError. Root cause not yet isolated
    (suspected Postgres connection/transaction-state interaction between
    the nested `transaction.atomic()` in `IdempotencyService.begin()` and
    pytest-django's per-test rollback wrapper under Testcontainers). Not
    skipped outright so it keeps failing loudly in CI until root-caused."""
    key = str(uuid.uuid4())
    first_code = f"IDEMP-{uuid.uuid4().hex[:8]}"
    other_code = f"IDEMP-{uuid.uuid4().hex[:8]}"

    first = admin_client.post(
        "/api/v1/products", {"code": first_code, "name": "A"}, format="json", HTTP_IDEMPOTENCY_KEY=key
    )
    assert first.status_code == 201

    second = admin_client.post(
        "/api/v1/products", {"code": other_code, "name": "B"}, format="json", HTTP_IDEMPOTENCY_KEY=key
    )
    assert second.status_code == 409
    assert second.json()["code"] == "IDEMP-REPLAY"


@pytest.mark.django_db
def test_missing_idempotency_key_on_required_endpoint_returns_400(admin_client):
    resp = admin_client.post(
        "/api/v1/products", {"code": f"IDEMP-{uuid.uuid4().hex[:8]}", "name": "No Key"}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_idempotency_key_is_scoped_per_tenant(tenant):
    """The same Idempotency-Key used by two different tenants must not
    collide — the (tenant, operation, key) tuple is the real identity."""
    from apps.foundation.infrastructure.models import Tenant

    other_tenant = Tenant.objects.create(id=uuid.uuid4(), code=f"tenant-{uuid.uuid4().hex[:8]}", name="Other")
    client_a = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
    client_b = make_client(tenant_id=other_tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")

    key = str(uuid.uuid4())
    resp_a = client_a.post(
        "/api/v1/products", {"code": "SHARED-KEY-A", "name": "A"}, format="json", HTTP_IDEMPOTENCY_KEY=key
    )
    resp_b = client_b.post(
        "/api/v1/products", {"code": "SHARED-KEY-B", "name": "B"}, format="json", HTTP_IDEMPOTENCY_KEY=key
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    assert resp_a.json()["id"] != resp_b.json()["id"]
