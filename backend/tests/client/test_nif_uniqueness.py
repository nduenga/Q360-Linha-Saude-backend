"""Decisão R1 (2026-10-14): NIF obrigatório para todo o cliente, no formato
do seu tipo, e único por tenant; o NIF da pessoa segura é opcional mas, quando
indicado, é único no tomador — a mesma pessoa pode ter ficha, com o NIF, em
tomadores diferentes (revisto em 2026-10-15). Garantido no serviço e na base de
dados."""
from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.client.infrastructure.models import Proposer
from tests.client.test_member_nif import _titular
from tests.client.test_members import _proposer


@pytest.mark.django_db
def test_member_nif_is_unique_per_proposer_on_create_and_update(admin_client):
    proposer = _proposer(admin_client)["id"]
    first = _titular(admin_client, proposer, nif="123456789LA042")
    assert first.status_code == 201, first.data

    duplicate = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer, "relationshipCode": "CONJUGE", "dateOfBirth": "1986-05-20",
         "nif": "123456789la042"},
        format="json",
    )
    assert duplicate.status_code == 409, duplicate.data

    spouse = admin_client.post(
        "/api/v1/members",
        {"proposerId": proposer, "relationshipCode": "CONJUGE", "dateOfBirth": "1986-05-20",
         "nif": "123456789LA043"},
        format="json",
    ).data
    taken = admin_client.put(
        f"/api/v1/members/{spouse['id']}",
        {"relationshipCode": "CONJUGE", "dateOfBirth": "1986-05-20", "nif": "123456789LA042", "rowVersion": 0},
        format="json",
    )
    assert taken.status_code == 409, taken.data
    # o próprio NIF pode ser reenviado sem conflito
    same = admin_client.put(
        f"/api/v1/members/{spouse['id']}",
        {"relationshipCode": "CONJUGE", "dateOfBirth": "1986-05-20", "nif": "123456789LA043", "rowVersion": 0},
        format="json",
    )
    assert same.status_code == 200, same.data


@pytest.mark.django_db
def test_the_same_person_can_have_the_nif_in_two_proposers(admin_client):
    """Colaborador de uma empresa e titular de uma apólice individual."""
    company = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "ORGANISATION", "displayName": "Empresa", "nif": "5417000002",
         "email": "rh@example.com", "phone": "+244900000000"},
        format="json",
    )
    assert company.status_code == 201, company.data
    individual = _proposer(admin_client)["id"]

    in_company = _titular(admin_client, company.data["id"], nif="123456789LA044")
    assert in_company.status_code == 201, in_company.data
    in_individual = _titular(admin_client, individual, nif="123456789LA044")
    assert in_individual.status_code == 201, in_individual.data
    assert in_company.data["id"] != in_individual.data["id"]


@pytest.mark.django_db
def test_editing_a_proposer_to_an_existing_nif_is_a_conflict(admin_client):
    taken = _proposer(admin_client)
    other = _proposer(admin_client)
    response = admin_client.put(
        f"/api/v1/proposers/{other['id']}",
        {"displayName": "Holder", "nif": taken["nif"], "dateOfBirth": "1985-04-12",
         "email": "holder@example.com", "phone": "+244900000000", "rowVersion": other["rowVersion"]},
        format="json",
    )
    assert response.status_code == 409, response.data


@pytest.mark.django_db
def test_database_requires_a_nif_matching_the_client_type(tenant):
    def insert(**fields):
        with transaction.atomic():
            Proposer.all_tenants.create(tenant_id=tenant.id, display_name="X", attributes_json={}, **fields)

    with pytest.raises(IntegrityError):
        insert(proposer_type="INDIVIDUAL", nif=None)
    with pytest.raises(IntegrityError):
        insert(proposer_type="INDIVIDUAL", nif="5417000000")  # NIF de empresa num particular
    with pytest.raises(IntegrityError):
        insert(proposer_type="ORGANISATION", nif="123456789LA042")
    insert(proposer_type="ORGANISATION", nif="5417000000")
    with pytest.raises(IntegrityError):
        insert(proposer_type="ORGANISATION", nif="5417000000")  # único por tenant
