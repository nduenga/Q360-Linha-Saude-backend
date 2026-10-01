"""Q360-S3-02 acceptance criteria: "Relação válida • Dependente requer
titular • Datas coerentes" — see OPEN_DECISIONS.md#S03-RELATIONSHIP-001 for
why "dependente requer titular" is not enforced (no approved relationship
code catalogue exists)."""
from __future__ import annotations

import datetime

import pytest


_COUNTER = iter(range(100000000, 999999999))


def _proposer(client) -> dict:
    """Each call gets its own valid NIF: `registrationNumber` is mirrored in
    `nif`, which is unique per tenant."""
    return client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": f"{next(_COUNTER)}LA042",
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data


@pytest.mark.django_db
def test_create_and_get_member(admin_client):
    proposer = _proposer(admin_client)
    response = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "firstName": "João", "dateOfBirth": "1990-05-20"},
    )
    assert response.status_code == 201
    body = response.data
    assert body["proposerId"] == proposer["id"]
    assert body["status"] == "ACTIVE"

    get_response = admin_client.get(f"/api/v1/members/{body['id']}")
    assert get_response.status_code == 200


@pytest.mark.django_db
def test_future_date_of_birth_is_rejected(admin_client):
    proposer = _proposer(admin_client)
    future = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    response = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": future},
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_update_member_optimistic_lock(admin_client):
    proposer = _proposer(admin_client)
    member = admin_client.post(
        "/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR"}
    ).data
    ok = admin_client.put(
        f"/api/v1/members/{member['id']}", {"relationshipCode": "CONJUGE", "rowVersion": 0}
    )
    assert ok.status_code == 200
    stale = admin_client.put(
        f"/api/v1/members/{member['id']}", {"relationshipCode": "FILHO", "rowVersion": 0}
    )
    assert stale.status_code == 409
    assert stale.data["code"] == "VERSION-CONFLICT"


@pytest.mark.django_db
def test_list_members_filtered_by_proposer(admin_client):
    proposer_a = _proposer(admin_client)
    proposer_b = _proposer(admin_client)
    admin_client.post("/api/v1/members", {"proposerId": proposer_a["id"], "relationshipCode": "TITULAR"})
    admin_client.post("/api/v1/members", {"proposerId": proposer_b["id"], "relationshipCode": "TITULAR"})

    response = admin_client.get(f"/api/v1/members?proposerId={proposer_a['id']}")
    assert response.status_code == 200
    assert len(response.data["items"]) == 1
    assert response.data["items"][0]["proposerId"] == proposer_a["id"]


@pytest.mark.django_db
def test_delete_member_deactivates_it_with_optimistic_lock(admin_client):
    proposer = _proposer(admin_client)
    member = admin_client.post(
        "/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR"}
    ).data

    response = admin_client.delete(f"/api/v1/members/{member['id']}", {"rowVersion": 0}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == "INACTIVE"
    assert response.data["rowVersion"] == 1
