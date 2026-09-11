"""Q360-S3-01 acceptance criteria: "Campos obrigatórios validados •
Duplicados detectados • Tenant ownership"."""
from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_create_and_get_proposer(admin_client):
    response = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "Ana Silva"},
    )
    assert response.status_code == 201
    body = response.data
    assert set(body.keys()) == {
        "id", "proposerType", "externalReference", "displayName",
        "registrationNumber", "attributes", "status", "rowVersion",
    }
    assert body["status"] == "ACTIVE"
    assert body["rowVersion"] == 0

    get_response = admin_client.get(f"/api/v1/proposers/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.data["displayName"] == "Ana Silva"


@pytest.mark.django_db
def test_duplicate_external_reference_is_conflict(admin_client):
    admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "ORGANISATION", "displayName": "Acme", "externalReference": "EXT-1"},
    )
    response = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "ORGANISATION", "displayName": "Acme 2", "externalReference": "EXT-1"},
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_update_proposer_optimistic_lock(admin_client):
    proposer = admin_client.post(
        "/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "Original"}
    ).data
    ok = admin_client.put(
        f"/api/v1/proposers/{proposer['id']}", {"displayName": "Renamed", "rowVersion": 0}
    )
    assert ok.status_code == 200
    assert ok.data["rowVersion"] == 1

    stale = admin_client.put(
        f"/api/v1/proposers/{proposer['id']}", {"displayName": "Conflict", "rowVersion": 0}
    )
    assert stale.status_code == 409
    assert stale.data["code"] == "VERSION-CONFLICT"


@pytest.mark.django_db
def test_list_proposers_is_tenant_scoped(admin_client, tenant):
    from tests.client.conftest import make_client

    admin_client.post("/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "Mine"})
    other = make_client(tenant_id="11111111-1111-1111-1111-111111111111", roles=["ADMIN"], scope="q360.read")
    response = other.get("/api/v1/proposers")
    assert response.status_code == 200
    assert response.data["items"] == []
