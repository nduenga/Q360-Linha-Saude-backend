"""Q360-S2-01 acceptance criteria: "Versões identificáveis • Vigências não
se sobrepõem • Publicado fica imutável". Response shapes asserted here are
ART-006 `Product`/`ProductVersion` schemas verbatim (camelCase)."""
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
    DECISIONS_TAKEN.md#product-status-transition. Publishing a version never
    implicitly changes this - it is set explicitly. A Product is ACTIVE from
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
def test_create_and_publish_product_version(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "VER", "name": "Versioned"}).data

    v1 = admin_client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    )
    assert v1.status_code == 201
    assert v1.data["versionNo"] == 1
    assert v1.data["status"] == "DRAFT"

    published = admin_client.post(f"/api/v1/product-versions/{v1.data['id']}/publish")
    assert published.status_code == 200
    assert published.data["status"] == "PUBLISHED"

    republish = admin_client.post(f"/api/v1/product-versions/{v1.data['id']}/publish")
    assert republish.status_code == 409
    assert republish.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_list_product_versions(admin_client):
    """Pragmatic V1 addition (OPEN_DECISIONS.md#S04-LISTING-GAPS-001):
    ART-006 has no listProductVersions, but the frontend needs a way to
    show a product's versions without a per-browser cache.

    ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 2: the second version is no
    longer created via a second explicit POST (that would now correctly
    be rejected as an overlap — every version is open-ended, see Épico 3)
    but via editing the product, which auto-rolls the version forward."""
    product = admin_client.post("/api/v1/products", {"code": "VERLIST", "name": "VerList"}).data
    admin_client.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"})
    admin_client.put(
        f"/api/v1/products/{product['id']}", {"name": "VerList renamed", "rowVersion": 0}
    )

    response = admin_client.get(f"/api/v1/products/{product['id']}/versions")
    assert response.status_code == 200
    assert response.data["page"]["totalElements"] == 2
    assert [v["versionNo"] for v in response.data["items"]] == [2, 1]
    assert response.data["items"][0]["status"] == "PUBLISHED"
    assert response.data["items"][1]["status"] == "RETIRED"


@pytest.mark.django_db
def test_editing_a_product_auto_creates_and_publishes_the_next_version(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "SEQ", "name": "Sequenced"}).data
    admin_client.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"})

    updated = admin_client.put(
        f"/api/v1/products/{product['id']}", {"name": "Sequenced renamed", "rowVersion": 0}
    )
    assert updated.status_code == 200

    versions = admin_client.get(f"/api/v1/products/{product['id']}/versions").data["items"]
    assert len(versions) == 2
    new_version = next(v for v in versions if v["versionNo"] == 2)
    assert new_version["status"] == "PUBLISHED"
    assert new_version["effectiveTo"] is None


@pytest.mark.django_db
def test_overlapping_effective_dates_are_rejected(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "OVL", "name": "Overlap"}).data
    admin_client.post(
        f"/api/v1/products/{product['id']}/versions",
        {"effectiveFrom": "2026-01-01", "effectiveTo": "2026-12-31"},
    )
    response = admin_client.post(
        f"/api/v1/products/{product['id']}/versions",
        {"effectiveFrom": "2026-06-01", "effectiveTo": "2026-08-31"},
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_two_explicit_open_ended_versions_always_overlap(admin_client):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 3: every version is open-ended
    (no effectiveTo), so a second version can only ever coexist with the
    first by retiring it first — which the explicit create-version
    endpoint does not do (see create_next_version for the real path, used
    automatically when a product with an existing version is edited)."""
    product = admin_client.post("/api/v1/products", {"code": "OPEN", "name": "Open ended"}).data
    admin_client.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2025-01-01"})
    response = admin_client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"
