"""ROADMAP_ANGOLA_CUSTOMIZATION.md Epico 6: PATCH/DELETE for a DRAFT
DocumentTemplateVersion, rejection once PUBLISHED, and the dedicated
retire endpoint (OD-ANGOLA-006) as the safe way to take a PUBLISHED
template out of use."""
from __future__ import annotations

import pytest


def _create(admin_client, code: str) -> dict:
    return admin_client.post(
        "/api/v1/document-templates",
        {"templateCode": code, "storageRef": "internal://original", "effectiveFrom": "2026-01-01"},
        format="json",
    ).data


@pytest.mark.django_db
def test_patch_draft_template_updates_storage_ref_and_checksum(admin_client):
    created = _create(admin_client, "CRUD-DT-1")

    response = admin_client.patch(
        f"/api/v1/document-templates/{created['id']}",
        {"storageRef": "internal://renamed"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "DRAFT"
    assert response.data["checksum"] != created["checksum"]


@pytest.mark.django_db
def test_delete_draft_template_removes_it(admin_client):
    created = _create(admin_client, "CRUD-DT-2")

    response = admin_client.delete(f"/api/v1/document-templates/{created['id']}")
    assert response.status_code == 204

    listing = admin_client.get("/api/v1/document-templates")
    assert all(item["id"] != created["id"] for item in listing.data["items"])


@pytest.mark.django_db
def test_patch_published_template_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-DT-3")
    admin_client.post(f"/api/v1/document-templates/{created['id']}/publish")

    response = admin_client.patch(
        f"/api/v1/document-templates/{created['id']}",
        {"storageRef": "internal://should-fail"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_delete_published_template_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-DT-4")
    admin_client.post(f"/api/v1/document-templates/{created['id']}/publish")

    response = admin_client.delete(f"/api/v1/document-templates/{created['id']}")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_retire_published_template_marks_it_retired(admin_client):
    created = _create(admin_client, "CRUD-DT-5")
    admin_client.post(f"/api/v1/document-templates/{created['id']}/publish")

    response = admin_client.post(f"/api/v1/document-templates/{created['id']}/retire")
    assert response.status_code == 200
    assert response.data["status"] == "RETIRED"


@pytest.mark.django_db
def test_retire_draft_template_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-DT-6")

    response = admin_client.post(f"/api/v1/document-templates/{created['id']}/retire")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"
