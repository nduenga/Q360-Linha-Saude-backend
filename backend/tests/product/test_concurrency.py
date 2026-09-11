"""Regression tests for the TOCTOU races fixed in application/use_cases.py
and application/product_service.py: read-then-save was replaced with
conditional UPDATE / `select_for_update()` specifically so that two
concurrent requests can never both succeed at something DOC-004 s7 says
must happen exactly once (publish) or never overlap (effective dates).

Uses `transaction=True` and real threads so the two requests genuinely run
in separate DB transactions/connections, unlike the default django_db
fixture (single wrapped transaction) which cannot exhibit this race at all.
"""
from __future__ import annotations

import threading

import pytest
from django.db import connection

from tests.product.conftest import make_client


def _run_concurrently(*targets: callable) -> list:
    results: list = [None] * len(targets)
    barrier = threading.Barrier(len(targets))

    def _wrapped(index: int, fn: callable) -> None:
        barrier.wait()
        try:
            results[index] = fn()
        finally:
            connection.close()

    threads = [threading.Thread(target=_wrapped, args=(i, fn)) for i, fn in enumerate(targets)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


@pytest.mark.django_db(transaction=True)
def test_concurrent_publish_only_one_succeeds(tenant):
    client = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
    product = client.post("/api/v1/products", {"code": "RACE", "name": "Race"}).data
    version = client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    ).data

    def publish():
        return client.post(f"/api/v1/product-versions/{version['id']}/publish").status_code

    statuses = _run_concurrently(publish, publish)

    assert sorted(statuses) == [200, 409]


@pytest.mark.django_db(transaction=True)
def test_concurrent_pricing_parameter_set_publish_only_one_succeeds(tenant):
    client = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
    created = client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": "RACE-CFG",
            "effectiveFrom": "2026-01-01",
            "parameters": [{"code": "X", "valueType": "INTEGER", "value": 1}],
        },
        format="json",
    ).data

    def publish():
        return client.post(
            f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish"
        ).status_code

    statuses = _run_concurrently(publish, publish)

    assert sorted(statuses) == [200, 409]
