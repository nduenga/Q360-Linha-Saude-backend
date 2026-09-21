"""ROADMAP_ANGOLA_CUSTOMIZATION.md OD-003 (OPEN_DECISIONS.md
#S03-RELATIONSHIP-001, Product Owner decision 2026-09-21): a real,
DB-backed relationship-code catalogue including ascendants (pais e
avós), enforced when creating/updating a Member."""
from __future__ import annotations

import pytest


def _proposer(client) -> str:
    return client.post("/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "Holder"}).data["id"]


@pytest.mark.django_db
def test_relationship_catalog_has_5_codes_including_ascendant(admin_client):
    response = admin_client.get("/api/v1/relationship-codes")
    assert response.status_code == 200
    codes = {item["code"]: item["category"] for item in response.data["items"]}
    assert codes == {
        "TITULAR": "TITULAR",
        "CONJUGE": "SPOUSE",
        "FILHO": "CHILD",
        "ASCENDENTE": "ASCENDANT",
        "OUTRO": "OTHER",
    }


@pytest.mark.django_db
def test_create_member_with_ascendant_relationship_succeeds(admin_client):
    proposer_id = _proposer(admin_client)
    response = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer_id, "relationshipCode": "ASCENDENTE", "firstName": "Mae"},
    )
    assert response.status_code == 201
    assert response.data["relationshipCode"] == "ASCENDENTE"


@pytest.mark.django_db
def test_create_member_with_unknown_relationship_code_is_rejected(admin_client):
    proposer_id = _proposer(admin_client)
    response = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer_id, "relationshipCode": "SOBRINHO", "firstName": "X"},
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_update_member_with_unknown_relationship_code_is_rejected(admin_client):
    proposer_id = _proposer(admin_client)
    member = admin_client.post(
        "/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "TITULAR"}
    ).data

    response = admin_client.put(
        f"/api/v1/members/{member['id']}", {"relationshipCode": "SOBRINHO", "rowVersion": 0}
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"
