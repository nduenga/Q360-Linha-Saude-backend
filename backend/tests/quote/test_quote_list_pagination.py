"""`GET /quotes`: 12 cotações por página por omissão, pesquisa no servidor e
contagens por estado para os indicadores da lista."""
from __future__ import annotations

import pytest

from apps.quote.infrastructure.models import Quote
from tests.quote.test_quotes import _quote_scope

URL = "/api/v1/quotes"


@pytest.fixture
def fifteen_quotes(admin_client, tenant):
    scope = _quote_scope(admin_client, code_suffix="paging")
    ids = []
    for _ in range(15):
        created = admin_client.post(URL, {"proposerId": scope["proposerId"], "planId": scope["planId"]}, format="json")
        assert created.status_code == 201, created.data
        ids.append(created.data["id"])
    Quote.all_tenants.filter(id__in=ids[:4], tenant_id=tenant.id).update(status="REJECTED")
    return ids


@pytest.mark.django_db
def test_default_page_has_12_quotes(admin_client, fifteen_quotes):
    first = admin_client.get(URL).data
    assert len(first["items"]) == 12
    assert first["page"] == {"page": 0, "size": 12, "totalElements": 15, "totalPages": 2}
    second = admin_client.get(f"{URL}?page=1").data
    assert len(second["items"]) == 3
    assert not {q["id"] for q in first["items"]} & {q["id"] for q in second["items"]}


@pytest.mark.django_db
def test_explicit_size_still_wins(admin_client, fifteen_quotes):
    data = admin_client.get(f"{URL}?size=200").data
    assert len(data["items"]) == 15 and data["page"]["size"] == 200


@pytest.mark.django_db
def test_status_counts_ignore_status_filter_and_search(admin_client, fifteen_quotes):
    everything = admin_client.get(URL).data
    assert everything["statusCounts"] == {"DRAFT": 11, "REJECTED": 4}
    assert everything["statusCountsTotal"] == 15

    rejected = admin_client.get(f"{URL}?status=REJECTED").data
    assert rejected["page"]["totalElements"] == 4
    assert all(q["status"] == "REJECTED" for q in rejected["items"])
    assert rejected["statusCounts"] == everything["statusCounts"]


@pytest.mark.django_db
def test_search_by_id_prefix(admin_client, fifteen_quotes):
    target = fifteen_quotes[7]
    data = admin_client.get(f"{URL}?q={target[:8].upper()}").data
    assert [q["id"] for q in data["items"]] == [target]
    assert data["statusCountsTotal"] == 15
    assert admin_client.get(f"{URL}?q=nada-disto").data["items"] == []
