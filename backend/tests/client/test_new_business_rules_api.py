"""API: NIF por tipo, data de nascimento obrigatória, titular primeiro,
diferença de idade, limite configurável e reabertura de cotações rejeitadas."""
from __future__ import annotations

import pytest

_n = iter(range(100000000, 999999999))


def _individual(client, **over) -> dict:
    payload = {
        "proposerType": "INDIVIDUAL",
        "displayName": "Holder",
        "nif": f"{next(_n)}LA042",
        "dateOfBirth": "1985-03-10",
        "email": "holder@example.com",
        "phone": "+244900000000",
    }
    payload.update(over)
    return client.post("/api/v1/proposers", payload)


def _member(client, proposer_id, code, dob, **over):
    body = {"proposerId": proposer_id, "relationshipCode": code, "firstName": "X", "dateOfBirth": dob}
    body.update(over)
    return client.post("/api/v1/members", body)


# ------------------------------------------------------------------ NIF
@pytest.mark.django_db
@pytest.mark.parametrize("nif", ["5402132186", "123456789LA0421", "123456789LA04"])
def test_individual_rejects_wrong_length_nif(admin_client, nif):
    assert _individual(admin_client, nif=nif).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("nif", ["540213218", "54021321860", "123456789LA042"])
def test_organisation_rejects_anything_but_10_digits(admin_client, nif):
    response = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "ORGANISATION", "displayName": "Acme", "nif": nif, "email": "a@b.co", "phone": "+244900000000"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_organisation_accepts_10_digits_without_birth_date(admin_client):
    response = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "ORGANISATION", "displayName": "Acme", "nif": "5402132186", "email": "a@b.co", "phone": "+244900000000"},
    )
    assert response.status_code == 201, response.data


# ----------------------------------------------------- data de nascimento
@pytest.mark.django_db
def test_individual_proposer_requires_birth_date(admin_client):
    payload = {"proposerType": "INDIVIDUAL", "displayName": "H", "nif": "123456789LA042", "email": "h@e.co", "phone": "+2449"}
    response = admin_client.post("/api/v1/proposers", payload)
    assert response.status_code == 400
    assert any(e["field"] == "dateOfBirth" for e in response.data["fieldErrors"])


@pytest.mark.django_db
def test_member_requires_birth_date(admin_client):
    proposer = _individual(admin_client).data
    response = admin_client.post(
        "/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "firstName": "A"}
    )
    assert response.status_code == 400


# ----------------------------------------------------------- titular first
@pytest.mark.django_db
def test_titular_must_exist_before_other_relationships(admin_client):
    proposer = _individual(admin_client).data
    response = _member(admin_client, proposer["id"], "CONJUGE", "1986-01-01")
    assert response.status_code == 400
    assert "titular" in response.data["detail"].lower()
    assert _member(admin_client, proposer["id"], "TITULAR", "1985-03-10").status_code == 201
    assert _member(admin_client, proposer["id"], "CONJUGE", "1986-01-01").status_code == 201


@pytest.mark.django_db
def test_individual_cannot_have_two_titulars(admin_client):
    proposer = _individual(admin_client).data
    assert _member(admin_client, proposer["id"], "TITULAR", "1985-03-10").status_code == 201
    assert _member(admin_client, proposer["id"], "TITULAR", "1986-03-10").status_code == 409


# ------------------------------------------------------------ age gap 13y
@pytest.mark.django_db
def test_child_must_be_13_years_younger_than_titular(admin_client):
    proposer = _individual(admin_client).data
    _member(admin_client, proposer["id"], "TITULAR", "1985-03-10")
    assert _member(admin_client, proposer["id"], "FILHO", "1985-03-10").status_code == 400  # mesma idade
    assert _member(admin_client, proposer["id"], "FILHO", "1980-01-01").status_code == 400  # mais velho
    assert _member(admin_client, proposer["id"], "FILHO", "1998-01-01").status_code == 400  # 13 anos incompletos
    assert _member(admin_client, proposer["id"], "FILHO", "1998-03-10").status_code == 201  # exatamente 13


@pytest.mark.django_db
def test_ascendant_must_be_13_years_older_than_titular(admin_client):
    proposer = _individual(admin_client).data
    _member(admin_client, proposer["id"], "TITULAR", "1985-03-10")
    assert _member(admin_client, proposer["id"], "ASCENDENTE", "1990-01-01").status_code == 400
    assert _member(admin_client, proposer["id"], "ASCENDENTE", "1960-01-01").status_code == 201


@pytest.mark.django_db
def test_changing_titular_birth_date_cannot_break_existing_children(admin_client):
    proposer = _individual(admin_client).data
    titular = _member(admin_client, proposer["id"], "TITULAR", "1985-03-10").data
    _member(admin_client, proposer["id"], "FILHO", "2010-01-01")
    response = admin_client.put(
        f"/api/v1/members/{titular['id']}",
        {"firstName": "Pessoa", "relationshipCode": "TITULAR", "dateOfBirth": "2005-01-01", "rowVersion": titular["rowVersion"]},
    )
    assert response.status_code == 400


# -------------------------------------------- limite configurável (GTE)
@pytest.mark.django_db
def test_beneficiary_limit_is_configurable_from_system_parameters(admin_client):
    listing = admin_client.get("/api/v1/system-parameters").data
    items = listing["items"] if isinstance(listing, dict) and "items" in listing else listing
    param = next(p for p in items if p["code"] == "client.individual_max_beneficiaries")
    assert param["editable"] is True
    set_resp = admin_client.put(
        "/api/v1/system-parameters/client.individual_max_beneficiaries",
        {"value": 1, "reason": "Limite de teste", "rowVersion": param["rowVersion"]},
    )
    assert set_resp.status_code == 200, set_resp.data

    proposer = _individual(admin_client).data
    _member(admin_client, proposer["id"], "TITULAR", "1985-03-10")
    assert _member(admin_client, proposer["id"], "CONJUGE", "1986-01-01").status_code == 201
    assert _member(admin_client, proposer["id"], "FILHO", "2012-01-01").status_code == 400  # excede 1
