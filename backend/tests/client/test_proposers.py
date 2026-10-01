"""Q360-S3-01 acceptance criteria: "Campos obrigatórios validados •
Duplicados detectados • Tenant ownership".

registrationNumber (NIF)/email/phone are mandatory on create (Product
Owner decision, 2026-09-26) — see apps/client/interfaces/serializers.py's
ProposerCreateRequestSerializer docstring.
"""
from __future__ import annotations

import pytest


def _valid_payload(**overrides) -> dict:
    payload = {
        "proposerType": "INDIVIDUAL",
        "displayName": "Ana Silva",
        "registrationNumber": "123456789LA042",
        "email": "ana@example.com",
        "phone": "+244900000000",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_create_and_get_proposer(admin_client):
    response = admin_client.post("/api/v1/proposers", _valid_payload())
    assert response.status_code == 201
    body = response.data
    assert set(body.keys()) == {
        "id", "proposerType", "externalReference", "displayName",
        "nif", "registrationNumber", "email", "phone", "attributes", "status", "rowVersion",
    }
    assert body["status"] == "ACTIVE"
    assert body["rowVersion"] == 0
    assert body["email"] == "ana@example.com"
    assert body["phone"] == "+244900000000"
    assert body["nif"] == "123456789LA042"

    get_response = admin_client.get(f"/api/v1/proposers/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.data["displayName"] == "Ana Silva"


@pytest.mark.django_db
def test_create_proposer_without_registration_number_is_rejected(admin_client):
    payload = _valid_payload(displayName="No NIF")
    del payload["registrationNumber"]
    response = admin_client.post("/api/v1/proposers", payload)
    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("nif", "expected"),
    [
        ("5402132186", "5402132186"),
        (" 002345678 la 041 ", "002345678LA041"),
    ],
)
def test_create_proposer_accepts_and_normalises_agt_nif(admin_client, nif, expected):
    payload = _valid_payload(nif=nif)
    del payload["registrationNumber"]
    response = admin_client.post("/api/v1/proposers", payload)

    assert response.status_code == 201, response.data
    assert response.data["nif"] == expected
    assert response.data["registrationNumber"] == expected


@pytest.mark.django_db
@pytest.mark.parametrize("nif", ["540213218", "54021321860", "002345678L041", "5402132186A"])
def test_create_proposer_rejects_nif_outside_agt_formats(admin_client, nif):
    payload = _valid_payload(nif=nif)
    del payload["registrationNumber"]
    response = admin_client.post("/api/v1/proposers", payload)

    assert response.status_code == 400
    assert any(e["field"] == "nif" for e in response.data["fieldErrors"])


@pytest.mark.django_db
def test_nif_is_unique_within_a_tenant(admin_client):
    first_payload = _valid_payload(nif="5402132186")
    duplicate_payload = _valid_payload(displayName="Same NIF", nif="5402132186")
    del first_payload["registrationNumber"]
    del duplicate_payload["registrationNumber"]
    first = admin_client.post("/api/v1/proposers", first_payload)
    duplicate = admin_client.post("/api/v1/proposers", duplicate_payload)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_create_proposer_without_email_is_rejected(admin_client):
    payload = _valid_payload(displayName="No email")
    del payload["email"]
    response = admin_client.post("/api/v1/proposers", payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_proposer_without_phone_is_rejected(admin_client):
    payload = _valid_payload(displayName="No phone")
    del payload["phone"]
    response = admin_client.post("/api/v1/proposers", payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_duplicate_external_reference_is_conflict(admin_client):
    admin_client.post(
        "/api/v1/proposers",
        _valid_payload(proposerType="ORGANISATION", displayName="Acme", externalReference="EXT-1"),
    )
    response = admin_client.post(
        "/api/v1/proposers",
        _valid_payload(proposerType="ORGANISATION", displayName="Acme 2", externalReference="EXT-1"),
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_update_proposer_optimistic_lock(admin_client):
    proposer = admin_client.post("/api/v1/proposers", _valid_payload(displayName="Original")).data
    ok = admin_client.put(
        f"/api/v1/proposers/{proposer['id']}",
        {
            "displayName": "Renamed",
            "registrationNumber": proposer["registrationNumber"],
            "email": proposer["email"],
            "phone": proposer["phone"],
            "rowVersion": 0,
        },
    )
    assert ok.status_code == 200
    assert ok.data["rowVersion"] == 1

    stale = admin_client.put(
        f"/api/v1/proposers/{proposer['id']}",
        {
            "displayName": "Conflict",
            "registrationNumber": proposer["registrationNumber"],
            "email": proposer["email"],
            "phone": proposer["phone"],
            "rowVersion": 0,
        },
    )
    assert stale.status_code == 409
    assert stale.data["code"] == "VERSION-CONFLICT"


@pytest.mark.django_db
def test_list_proposers_is_tenant_scoped(admin_client, tenant):
    from tests.client.conftest import make_client

    admin_client.post("/api/v1/proposers", _valid_payload(displayName="Mine"))
    other = make_client(tenant_id="11111111-1111-1111-1111-111111111111", roles=["ADMIN"], scope="q360.read")
    response = other.get("/api/v1/proposers")
    assert response.status_code == 200
    assert response.data["items"] == []
