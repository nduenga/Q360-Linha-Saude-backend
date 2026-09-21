"""ROADMAP_ANGOLA_CUSTOMIZATION.md Epico 6: PATCH/DELETE for a DRAFT
RatingTable, rejection once PUBLISHED, and retire as the safe way to take
a PUBLISHED one out of use."""
from __future__ import annotations

import pytest


def _factors_payload() -> list[dict]:
    return [{"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "0-17"}, "factorValue": "0.80"}]


def _create(admin_client, code: str) -> dict:
    return admin_client.post(
        "/api/v1/rating-tables",
        {"code": code, "name": "Original", "effectiveFrom": "2026-01-01", "currencyCode": "AOA", "factors": _factors_payload()},
        format="json",
    ).data


@pytest.mark.django_db
def test_patch_draft_rating_table_updates_name_and_factors(admin_client, tenant):
    created = _create(admin_client, "CRUD-RT-1")

    response = admin_client.patch(
        f"/api/v1/rating-tables/{created['id']}",
        {
            "name": "Renamed",
            "currencyCode": "AOA",
            "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "70+"}, "factorValue": "3.50"}],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "DRAFT"

    from decimal import Decimal

    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.permissions import Role
    from apps.foundation.domain.tenant import TenantId
    from apps.pricing.infrastructure.models import RatingFactor

    actor = Actor(actor_id="tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    try:
        factors = list(
            RatingFactor.objects.filter(rating_table_id=created["id"]).values_list("factor_value", flat=True)
        )
        assert factors == [Decimal("3.50")]
    finally:
        CurrentActorProvider.reset(token)


@pytest.mark.django_db
def test_delete_draft_rating_table_removes_it(admin_client):
    created = _create(admin_client, "CRUD-RT-2")

    response = admin_client.delete(f"/api/v1/rating-tables/{created['id']}")
    assert response.status_code == 204

    listing = admin_client.get("/api/v1/rating-tables")
    assert all(item["id"] != created["id"] for item in listing.data["items"])


@pytest.mark.django_db
def test_patch_published_rating_table_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-RT-3")
    admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")

    response = admin_client.patch(
        f"/api/v1/rating-tables/{created['id']}",
        {"name": "Should Fail", "currencyCode": "AOA", "factors": _factors_payload()},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_delete_published_rating_table_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-RT-4")
    admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")

    response = admin_client.delete(f"/api/v1/rating-tables/{created['id']}")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_retire_published_rating_table_marks_it_retired(admin_client, tenant):
    import datetime

    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.permissions import Role
    from apps.foundation.domain.tenant import TenantId
    from apps.pricing.application.rating_table_service import resolve_rating_table

    created = _create(admin_client, "CRUD-RT-5")
    admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")

    response = admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/retire")
    assert response.status_code == 200
    assert response.data["status"] == "RETIRED"

    actor = Actor(actor_id="tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    try:
        assert resolve_rating_table(code="CRUD-RT-5", effective_date=datetime.date(2026, 6, 1)) is None
    finally:
        CurrentActorProvider.reset(token)


@pytest.mark.django_db
def test_retire_draft_rating_table_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-RT-6")

    response = admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/retire")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"
