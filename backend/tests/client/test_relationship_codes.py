
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
def test_relationship_catalog_hides_household_anchors_and_lists_family_relations(
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
        "DESCENDENTE": "DESCENDANT",
        "PAI": "ASCENDANT",
        "MAE": "ASCENDANT",
        "ASCENDENTE": "ASCENDANT",
        "OUTRO": "OTHER",
    }
    assert "TITULAR" not in codes
    assert "COLABORADOR" not in codes


@pytest.mark.django_db
def test_employee_relationship_is_available_for_organisation_household_anchor(admin_client):
    response = admin_client.get("/api/v1/relationship-codes?householdRole=EMPLOYEE")
    assert response.status_code == 200, response.data
    assert [(item["code"], item["category"]) for item in response.data["items"]] == [
        ("COLABORADOR", "COLLABORATOR")
    ]


@pytest.mark.django_db
def test_organisation_employee_heads_household_and_age_is_checked_against_employee(admin_client):
    proposer_response = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "ORGANISATION", "displayName": "Empresa", "nif": "5402132186",
         "email": "empresa@example.com", "phone": "+244900000000"},
    )
    assert proposer_response.status_code == 201, proposer_response.data
    proposer_id = proposer_response.data["id"]

    employee_response = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer_id, "relationshipCode": "TITULAR", "firstName": "Ana", "dateOfBirth": "1990-01-01"},
    )
    assert employee_response.status_code == 201, employee_response.data
    assert employee_response.data["relationshipCode"] == "COLABORADOR"

    household_response = admin_client.post(
        "/api/v1/households",
        {"proposerId": proposer_id, "primaryMemberId": employee_response.data["id"], "joinedAt": "2026-10-31"},
    )
    assert household_response.status_code == 201, household_response.data
    household_id = household_response.data["id"]

    underage_gap = admin_client.post(
        f"/api/v1/households/{household_id}/dependents",
        {"relationshipCode": "FILHO", "firstName": "Filho", "dateOfBirth": "2002-12-31", "joinedAt": "2026-10-31"},
    )
    assert underage_gap.status_code == 400
    valid_child = admin_client.post(
        f"/api/v1/households/{household_id}/dependents",
        {"relationshipCode": "FILHO", "firstName": "Filho", "dateOfBirth": "2003-01-01", "joinedAt": "2026-10-31"},
    )
    assert valid_child.status_code == 201, valid_child.data
    assert valid_child.data["relationshipCode"] == "FILHO"

    invalid_employee_update = admin_client.put(
        f"/api/v1/members/{employee_response.data['id']}",
        {"relationshipCode": "FILHO", "firstName": "Ana", "dateOfBirth": "1995-01-01",
         "rowVersion": employee_response.data["rowVersion"]},
    )
    assert invalid_employee_update.status_code == 400


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
        {"firstName": "Pessoa", 
            "relationshipCode": "SOBRINHO",
            "rowVersion": member.get("rowVersion", 0),
        },
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"
