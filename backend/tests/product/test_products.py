"""Q360-S2-01 acceptance criteria (Product CRUD). Response shapes asserted
here are ART-006 `Product` schema verbatim (camelCase).

DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26): ProductVersion
was retired — a Plan belongs directly to a Product now (tests/product/
test_plans.py covers Plan CRUD/lifecycle; this file only covers Product
itself and delete-cascade behaviour)."""
from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_create_and_get_product(admin_client):
    response = admin_client.post("/api/v1/products", {"code": "HEALTH-ESSENTIAL", "name": "Essencial"})
    assert response.status_code == 201
    body = response.data
    assert set(body.keys()) == {"id", "code", "name", "description", "status", "rowVersion"}
    assert body["code"] == "HEALTH-ESSENTIAL"
    assert body["status"] == "ACTIVE"
    assert body["rowVersion"] == 0
    assert body["description"] is None

    get_response = admin_client.get(f"/api/v1/products/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.data["id"] == body["id"]


@pytest.mark.django_db
def test_duplicate_product_code_is_conflict(admin_client):
    admin_client.post("/api/v1/products", {"code": "DUP", "name": "First"})
    response = admin_client.post("/api/v1/products", {"code": "DUP", "name": "Second"})
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_get_missing_product_is_not_found(admin_client):
    response = admin_client.get("/api/v1/products/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404
    assert response.data["code"] == "NOT-FOUND"


@pytest.mark.django_db
def test_update_product_with_correct_row_version_succeeds(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "UPD", "name": "Original"}).data
    response = admin_client.put(
        f"/api/v1/products/{product['id']}",
        {"name": "Renamed", "description": "now described", "rowVersion": 0},
    )
    assert response.status_code == 200
    assert response.data["name"] == "Renamed"
    assert response.data["rowVersion"] == 1


@pytest.mark.django_db
def test_update_product_status(admin_client):
    """Pragmatic V1 addition, not in ART-006's ProductUpdateRequest - see
    DECISIONS_TAKEN.md#product-status-transition. A Product is ACTIVE from
    creation (Product Owner decision, 2026-09-25); this exercises moving it
    out of the catalogue and back, which a future product-management page
    will do through this same field."""
    product = admin_client.post("/api/v1/products", {"code": "ACTIVATE-ME", "name": "Activate"}).data
    assert product["status"] == "ACTIVE"

    response = admin_client.put(
        f"/api/v1/products/{product['id']}",
        {"name": product["name"], "rowVersion": 0, "status": "ARCHIVED"},
    )
    assert response.status_code == 200
    assert response.data["status"] == "ARCHIVED"

    # Omitting `status` leaves it unchanged (backward compatible).
    unchanged = admin_client.put(
        f"/api/v1/products/{product['id']}",
        {"name": "Still Archived", "rowVersion": 1},
    )
    assert unchanged.data["status"] == "ARCHIVED"


@pytest.mark.django_db
def test_update_product_with_stale_row_version_is_version_conflict(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "STALE", "name": "Original"}).data
    admin_client.put(f"/api/v1/products/{product['id']}", {"name": "First update", "rowVersion": 0})

    response = admin_client.put(
        f"/api/v1/products/{product['id']}", {"name": "Conflicting update", "rowVersion": 0}
    )
    assert response.status_code == 409
    assert response.data["code"] == "VERSION-CONFLICT"


@pytest.mark.django_db
def test_list_products_returns_page_envelope(admin_client):
    for i in range(3):
        admin_client.post("/api/v1/products", {"code": f"LIST-{i}", "name": f"Product {i}"})

    response = admin_client.get("/api/v1/products?size=2")
    assert response.status_code == 200
    assert set(response.data.keys()) == {"items", "page"}
    assert len(response.data["items"]) == 2
    assert response.data["page"] == {"page": 0, "size": 2, "totalElements": 3, "totalPages": 2}


@pytest.mark.django_db
def test_list_products_filtered_by_status(admin_client):
    """`?status=` is a pragmatic V1 addition (not in ART-006, same posture
    as the equivalent filter on PricingParameterSet/RatingTable/
    RuleVersion) - lets a product picker ask for ACTIVE only. A Product is
    ACTIVE from creation (Product Owner decision, 2026-09-25), so getting
    a non-ACTIVE one to filter out here means explicitly archiving it -
    exactly what a future product-management page would do."""
    archived = admin_client.post("/api/v1/products", {"code": "STATUS-ARCHIVED", "name": "Archived"}).data
    admin_client.put(
        f"/api/v1/products/{archived['id']}", {"name": "Archived", "rowVersion": 0, "status": "ARCHIVED"}
    )
    active = admin_client.post("/api/v1/products", {"code": "STATUS-ACTIVE", "name": "Active"}).data

    response = admin_client.get("/api/v1/products?status=ACTIVE")
    assert response.status_code == 200
    codes = {item["code"] for item in response.data["items"]}
    assert codes == {"STATUS-ACTIVE"}
    assert active["status"] == "ACTIVE"
    assert archived["code"] not in codes


@pytest.mark.django_db
def test_delete_product_without_plans(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "DEL-1", "name": "To delete"}).data

    response = admin_client.delete(f"/api/v1/products/{product['id']}")
    assert response.status_code == 204

    get_response = admin_client.get(f"/api/v1/products/{product['id']}")
    assert get_response.status_code == 404

    # A code freed by deletion must be reusable - proves the row is truly
    # gone, not just hidden by a soft-delete flag.
    recreated = admin_client.post("/api/v1/products", {"code": "DEL-1", "name": "Recreated"})
    assert recreated.status_code == 201


@pytest.mark.django_db
def test_delete_product_cascades_through_plans(admin_client):
    """Product Owner requirement (2026-09-25): deleting a product must
    work even when it already has plans - not only a fresh, plan-less
    one."""
    product = admin_client.post("/api/v1/products", {"code": "DEL-2", "name": "Has plan"}).data
    plan = admin_client.post(
        "/api/v1/plans", {"productId": product["id"], "code": "PLAN", "name": "A plan"}
    ).data

    response = admin_client.delete(f"/api/v1/products/{product['id']}")
    assert response.status_code == 204

    assert admin_client.get(f"/api/v1/products/{product['id']}").status_code == 404
    assert admin_client.get(f"/api/v1/plans/{plan['id']}").status_code == 404


@pytest.mark.django_db
def test_cannot_delete_product_once_a_quote_references_it(admin_client):
    """Still fail-safe underneath: a Quote that already pins one of this
    product's Plan rows must never be silently orphaned or corrupted
    (OD-ANGOLA-004) - the plain FK from `quote` to `plan`
    (0001_quote_baseline.py) makes Postgres itself refuse the delete; this
    asserts it surfaces as a clean 409, not a raw 500."""
    product = admin_client.post("/api/v1/products", {"code": "DEL-4", "name": "Quoted"}).data
    plan = admin_client.post(
        "/api/v1/plans", {"productId": product["id"], "code": "PLAN", "name": "A plan"}
    ).data
    proposer = admin_client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "dateOfBirth": "1985-04-12", "displayName": "Holder",
            "registrationNumber": "123456789LA042",
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data
    admin_client.post(
        "/api/v1/quotes",
        {
            "planId": plan["id"],
            "proposerId": proposer["id"],
        },
        format="json",
    )

    response = admin_client.delete(f"/api/v1/products/{product['id']}")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"

    still_there = admin_client.get(f"/api/v1/products/{product['id']}")
    assert still_there.status_code == 200


@pytest.mark.django_db
def test_delete_product_requires_product_manage_permission(admin_client, tenant):
    from tests.product.conftest import make_client

    product = admin_client.post("/api/v1/products", {"code": "DEL-3", "name": "Perm check"}).data
    subscriber_client = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write")

    response = subscriber_client.delete(f"/api/v1/products/{product['id']}")
    assert response.status_code == 403
    assert response.data["code"] == "AUTH-403"

    still_there = admin_client.get(f"/api/v1/products/{product['id']}")
    assert still_there.status_code == 200
