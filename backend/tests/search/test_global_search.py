"""Pesquisa global do back-office (`GET /search`): resultados agrupados,
isolamento por tenant e scope q360.read."""
from __future__ import annotations

import uuid

import pytest

from apps.foundation.infrastructure.models import Tenant
from tests.quote.conftest import make_client


def _client(tenant, scope="q360.read q360.write"):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=scope)


def _tenant():
    return Tenant.objects.create(id=uuid.uuid4(), code=f"tenant-{uuid.uuid4().hex[:8]}", name="Tenant")


def _proposer(client, name, nif):
    created = client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": name, "nif": nif, "dateOfBirth": "1985-04-12",
         "email": "pesquisa@example.com", "phone": "+244900000000"},
        format="json",
    )
    assert created.status_code == 201, created.data
    return created.data


@pytest.mark.django_db
def test_search_groups_results_and_stays_inside_the_tenant():
    mine, other = _tenant(), _tenant()
    client = _client(mine)
    found = _proposer(client, "Kilamba Pesquisa", "123456789LA101")
    _proposer(_client(other), "Kilamba Outro Tenant", "123456789LA102")

    response = client.get("/api/v1/search?q=kilamba")
    assert response.status_code == 200, response.data
    clients = next(g for g in response.data["groups"] if g["kind"] == "proposer")
    assert [i["id"] for i in clients["items"]] == [found["id"]]
    assert clients["items"][0]["href"] == f"/clientes/{found['id']}"
    assert response.data["total"] == 1

    by_nif = client.get("/api/v1/search?q=LA101").data
    assert by_nif["total"] == 1
    assert client.get("/api/v1/search?q=k").data == {"total": 0, "groups": []}  # mínimo 2 caracteres


@pytest.mark.django_db
def test_search_requires_the_read_scope():
    tenant = _tenant()
    assert _client(tenant, scope="q360.write").get("/api/v1/search?q=ab").status_code == 403
