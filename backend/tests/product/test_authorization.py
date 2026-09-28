"""Q360-S1-04 (tenant isolation) and the two-layer authorization model
(ART-006 OAuth2 scopes + DOC-001 s18 RBAC permissions) applied to the
product module."""
from __future__ import annotations

import uuid

import pytest

from tests.product.conftest import make_client


@pytest.mark.django_db
def test_cross_tenant_product_read_is_not_found_not_forbidden(admin_client, tenant):
    product = admin_client.post("/api/v1/products", {"code": "SECRET", "name": "Secret"}).data

    other_tenant_client = make_client(tenant_id=uuid.uuid4(), roles=["ADMIN"], scope="q360.read")
    response = other_tenant_client.get(f"/api/v1/products/{product['id']}")
    # DOC-001 s20: must not confirm existence to an unauthorised tenant.
    assert response.status_code == 404
    assert response.data["code"] == "NOT-FOUND"


@pytest.mark.django_db
def test_cross_tenant_products_are_not_listed(admin_client, tenant):
    admin_client.post("/api/v1/products", {"code": "MINE", "name": "Mine"})

    other_tenant_client = make_client(tenant_id=uuid.uuid4(), roles=["ADMIN"], scope="q360.read")
    response = other_tenant_client.get("/api/v1/products")
    assert response.status_code == 200
    assert response.data["items"] == []


@pytest.mark.django_db
def test_create_product_without_write_scope_is_forbidden(tenant):
    # Has the DOC-001 role/permission but not the ART-006 OAuth2 scope.
    client = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read")
    response = client.post("/api/v1/products", {"code": "X", "name": "X"})
    assert response.status_code == 403
    assert response.data["code"] == "AUTH-403"


@pytest.mark.django_db
def test_create_product_with_scope_but_wrong_role_is_forbidden(tenant):
    # Has the ART-006 scope but the DOC-001 s18 matrix gives SUBSCRIBER no
    # product:manage permission.
    client = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.write")
    response = client.post("/api/v1/products", {"code": "X", "name": "X"})
    assert response.status_code == 403
    assert response.data["code"] == "AUTH-403"


@pytest.mark.django_db
def test_create_plan_requires_admin_scope_not_write(tenant):
    # createPlan's ART-006 security block is q360.admin, not q360.write.
    client = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write")
    product = client.post("/api/v1/products", {"code": "SCOPE", "name": "Scope"}).data
    plan = client.post("/api/v1/plans", {"productId": product["id"], "code": "P1", "name": "P1"})
    assert plan.status_code == 403
    assert plan.data["code"] == "AUTH-403"


@pytest.mark.django_db
def test_edit_and_delete_plan_require_product_manage_permission(admin_client, tenant):
    """Same DOC-001 s18 gate as creating a plan (require_permission(PRODUCT_MANAGE))
    - SUBSCRIBER can read a plan but not edit/delete it."""
    product = admin_client.post("/api/v1/products", {"code": "PLAN-PERM", "name": "Plan Perm"}).data
    plan = admin_client.post(
        "/api/v1/plans", {"productId": product["id"], "code": "PERM", "name": "Original"}
    ).data

    subscriber_client = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write")

    patch_response = subscriber_client.patch(
        f"/api/v1/plans/{plan['id']}", {"name": "Hijacked", "rowVersion": plan["rowVersion"]}, format="json"
    )
    assert patch_response.status_code == 403
    assert patch_response.data["code"] == "AUTH-403"

    delete_response = subscriber_client.delete(f"/api/v1/plans/{plan['id']}")
    assert delete_response.status_code == 403
    assert delete_response.data["code"] == "AUTH-403"

    still_there = admin_client.get(f"/api/v1/plans/{plan['id']}")
    assert still_there.status_code == 200
    assert still_there.data["name"] == "Original"


@pytest.mark.django_db
def test_unauthenticated_request_is_401_not_403():
    from rest_framework.test import APIClient

    response = APIClient().get("/api/v1/products")
    assert response.status_code == 401
    assert response.data["code"] == "AUTH-401"
