
"""Testes do catálogo de relações familiares por tenant."""
from __future__ import annotations

import pytest


def _proposer(client) -> str:
    response = client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": "123456789LA042",
            "dateOfBirth": "1990-05-14",
            "email": "monteiroui8@gmail.com",
            "phone": "+244900000000",
        },
    )
    assert response.status_code == 201, response.data
    return response.data["id"]


def _create_titular(client, proposer_id: str) -> dict:
    response = client.post(
        "/api/v1/members",
        {
            "proposerId": proposer_id,
            "relationshipCode": "TITULAR",
            "firstName": "Titular",
            "dateOfBirth": "1985-01-01",
        },
    )
    assert response.status_code == 201, response.data
    return response.data


@pytest.mark.django_db
def test_relationship_catalog_hides_titular_and_has_4_public_codes(
    admin_client,
):
    response = admin_client.get("/api/v1/relationship-codes")

    assert response.status_code == 200, response.data

    codes = {
        item["code"]: item["category"]
        for item in response.data["items"]
    }

    assert codes == {
        "CONJUGE": "SPOUSE",
        "FILHO": "CHILD",
        "ASCENDENTE": "ASCENDANT",
        "OUTRO": "OTHER",
    }
    assert "TITULAR" not in codes


@pytest.mark.django_db
def test_create_member_with_ascendant_relationship_succeeds(admin_client):
    proposer_id = _proposer(admin_client)
    _create_titular(admin_client, proposer_id)

    response = admin_client.post(
        "/api/v1/members",
        {
            "proposerId": proposer_id,
            "relationshipCode": "ASCENDENTE",
            "firstName": "Mae",
            "dateOfBirth": "1960-05-14",
        },
    )

    assert response.status_code == 201, response.data
    assert response.data["relationshipCode"] == "ASCENDENTE"


@pytest.mark.django_db
def test_create_member_with_unknown_relationship_code_is_rejected(
    admin_client,
):
    proposer_id = _proposer(admin_client)
    _create_titular(admin_client, proposer_id)

    response = admin_client.post(
        "/api/v1/members",
        {
            "proposerId": proposer_id,
            "relationshipCode": "SOBRINHO",
            "firstName": "X",
            "dateOfBirth": "1990-05-14",
        },
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_update_member_with_unknown_relationship_code_is_rejected(
    admin_client,
):
    proposer_id = _proposer(admin_client)
    member = _create_titular(admin_client, proposer_id)

    response = admin_client.put(
        f"/api/v1/members/{member['id']}",
        {
            "relationshipCode": "SOBRINHO",
            "rowVersion": member.get("rowVersion", 0),
        },
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"
