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
            "dateOfBirth": "1985-04-12",
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
        {"firstName": "Pessoa", "proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": future},
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"



@pytest.mark.django_db
def test_update_member_optimistic_lock(admin_client):
    proposer = _proposer(admin_client)

    titular = admin_client.post(
        "/api/v1/members",
        {"firstName": "Pessoa", 
            "proposerId": proposer["id"],
            "relationshipCode": "TITULAR",
            "dateOfBirth": "1990-05-20",
        },
    )
    assert titular.status_code == 201, titular.data

    member = admin_client.post(
        "/api/v1/members",
        {"firstName": "Pessoa", 
            "proposerId": proposer["id"],
            "relationshipCode": "OUTRO",
            "dateOfBirth": "1992-06-15",
        },
    )
    assert member.status_code == 201, member.data
    member = member.data

    ok = admin_client.put(
        f"/api/v1/members/{member['id']}",
        {"firstName": "Pessoa", 
            "relationshipCode": "CONJUGE",
            "dateOfBirth": "1992-06-15",
            "rowVersion": 0,
        },
    )
    assert ok.status_code == 200, ok.data

    stale = admin_client.put(
        f"/api/v1/members/{member['id']}",
        {"firstName": "Pessoa", 
            # válido em tudo exceto na versão: FILHO nascido em 1992 violaria a
            # regra de idade face ao titular (400) e esconderia o conflito.
            "relationshipCode": "OUTRO",
            "dateOfBirth": "1992-06-15",
            "rowVersion": 0,
        },
    )
    assert stale.status_code == 409, stale.data
    assert stale.data["code"] == "VERSION-CONFLICT"




@pytest.mark.django_db
def test_list_members_filtered_by_proposer(admin_client):
    proposer_a = _proposer(admin_client)
    proposer_b = _proposer(admin_client)
    admin_client.post("/api/v1/members", {"firstName": "Pessoa", "proposerId": proposer_a["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-05-20"})
    admin_client.post("/api/v1/members", {"firstName": "Pessoa", "proposerId": proposer_b["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-05-20"})

    response = admin_client.get(f"/api/v1/members?proposerId={proposer_a['id']}")
    assert response.status_code == 200
    assert len(response.data["items"]) == 1
    assert response.data["items"][0]["proposerId"] == proposer_a["id"]


@pytest.mark.django_db
def test_delete_member_deactivates_it_with_optimistic_lock(admin_client):
    proposer = _proposer(admin_client)
    member = admin_client.post(
        "/api/v1/members", {"firstName": "Pessoa", "proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-05-20"}
    ).data

    response = admin_client.delete(f"/api/v1/members/{member['id']}", {"rowVersion": 0}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == "INACTIVE"
    assert response.data["rowVersion"] == 1


@pytest.mark.django_db
def test_member_requires_name_and_rejects_unknown_fields(admin_client):
    """F10: sem nome, ou com um campo com nome errado (p.ex. fullName), dá 400
    em vez de gravar uma pessoa segura sem nome."""
    proposer = admin_client.post("/api/v1/proposers", {
        "proposerType": "INDIVIDUAL", "displayName": "Sem Nome", "registrationNumber": "009988771LA048",
        "dateOfBirth": "1990-01-01", "email": "sem.nome@example.com", "phone": "+244900000001"}).data
    base = {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    missing = admin_client.post("/api/v1/members", base, format="json")
    assert missing.status_code == 400 and missing.data["fieldErrors"][0]["field"] == "firstName"
    blank = admin_client.post("/api/v1/members", {**base, "firstName": "  "}, format="json")
    assert blank.status_code == 400
    unknown = admin_client.post("/api/v1/members", {**base, "fullName": "Rui Costa", "gender": "M"}, format="json")
    assert unknown.status_code == 400
    messages = {e["field"]: e["message"] for e in unknown.data["fieldErrors"]}
    assert "firstName e lastName" in messages["fullName"] and "sexCode" in messages["gender"]
    ok = admin_client.post("/api/v1/members", {**base, "firstName": " Rui ", "lastName": "Costa"}, format="json")
    assert ok.status_code == 201, ok.data
    assert ok.data["firstName"] == "Rui"
