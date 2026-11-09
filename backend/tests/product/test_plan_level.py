"""Planos com as mesmas coberturas no mesmo produto: permitidos quando declaram
níveis diferentes da gama (capitais diferentes), recusados quando são iguais."""
from __future__ import annotations

import pytest


def _plan(client, product_id, code, settings=None):
    body = {"productId": product_id, "code": code, "name": code}
    if settings is not None:
        body["settings"] = settings
    return client.post("/api/v1/plans", body, format="json")


@pytest.mark.django_db
def test_same_coverages_need_a_different_level(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "GAMA", "name": "Gama"}).data
    base = {"segment": "INDIVIDUAL_FAMILY"}
    assert _plan(admin_client, product["id"], "PREMIUM", {**base, "level": 3}).status_code == 201
    assert _plan(admin_client, product["id"], "PREMIUM-PLUS", {**base, "level": 4}).status_code == 201
    repeated = _plan(admin_client, product["id"], "PREMIUM-COPIA", {**base, "level": 4})
    assert repeated.status_code == 409


@pytest.mark.django_db
def test_level_must_be_a_positive_whole_number(admin_client):
    product = admin_client.post("/api/v1/products", {"code": "GAMA2", "name": "Gama 2"}).data
    assert _plan(admin_client, product["id"], "ERRADO", {"segment": "GROUP", "level": 0}).status_code == 400
    assert _plan(admin_client, product["id"], "ERRADO2", {"segment": "GROUP", "level": "4"}).status_code == 400
