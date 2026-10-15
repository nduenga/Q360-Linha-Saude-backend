"""NIF do beneficiário (pessoa segura): opcional; validado quando enviado;
omitido numa edição não apaga o valor guardado."""
from __future__ import annotations

import pytest

from tests.client.test_members import _proposer


def _titular(client, proposer_id, **extra):
    return client.post(
        "/api/v1/members",
        {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": "1985-04-12", **extra},
        format="json",
    )


@pytest.mark.django_db
def test_member_nif_is_optional(admin_client):
    created = _titular(admin_client, _proposer(admin_client)["id"])
    assert created.status_code == 201, created.data
    assert created.data["nif"] is None


@pytest.mark.django_db
def test_member_nif_is_normalised_and_validated(admin_client):
    proposer_id = _proposer(admin_client)["id"]
    bad = _titular(admin_client, proposer_id, nif="12345")
    assert bad.status_code == 400
    ok = _titular(admin_client, proposer_id, nif=" 123456789 la 042 ")
    assert ok.status_code == 201, ok.data
    assert ok.data["nif"] == "123456789LA042"


@pytest.mark.django_db
def test_update_without_nif_keeps_it_and_null_removes_it(admin_client):
    member = _titular(admin_client, _proposer(admin_client)["id"], nif="123456789LA042").data
    kept = admin_client.put(
        f"/api/v1/members/{member['id']}",
        {"relationshipCode": "TITULAR", "dateOfBirth": "1985-04-12", "rowVersion": 0},
        format="json",
    )
    assert kept.status_code == 200, kept.data
    assert kept.data["nif"] == "123456789LA042"
    cleared = admin_client.put(
        f"/api/v1/members/{member['id']}",
        {"relationshipCode": "TITULAR", "dateOfBirth": "1985-04-12", "nif": None, "rowVersion": 1},
        format="json",
    )
    assert cleared.status_code == 200, cleared.data
    assert cleared.data["nif"] is None
