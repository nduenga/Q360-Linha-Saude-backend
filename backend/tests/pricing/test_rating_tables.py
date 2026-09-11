"""Q360-S4-01 acceptance criteria: "Versão e vigência obrigatórias •
Publicada é imutável"."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.tenant import TenantId
from apps.pricing.application.rating_table_service import resolve_factor, resolve_rating_table


def _factors_payload() -> list[dict]:
    return [
        {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "0-17"}, "factorValue": "0.80"},
        {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "30-39"}, "factorValue": "1.00"},
        {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "70+"}, "factorValue": "3.80"},
        {"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00", "priority": -1},
    ]


@pytest.mark.django_db
def test_create_rating_table_with_factors(admin_client):
    response = admin_client.post(
        "/api/v1/rating-tables",
        {
            "code": "AGE-TABLE",
            "name": "Age Rating Table",
            "effectiveFrom": "2026-01-01",
            "currencyCode": "AOA",
            "factors": _factors_payload(),
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.data
    assert set(body.keys()) == {"id", "code", "versionNo", "effectiveFrom", "effectiveTo", "status", "checksum"}
    assert body["versionNo"] == 1
    assert body["status"] == "DRAFT"


@pytest.mark.django_db
def test_factor_value_must_be_decimal_string(admin_client):
    response = admin_client.post(
        "/api/v1/rating-tables",
        {
            "code": "BAD",
            "name": "Bad",
            "effectiveFrom": "2026-01-01",
            "factors": [{"factorCode": "X", "dimensions": {}, "factorValue": 1.5}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_at_least_one_factor_required(admin_client):
    response = admin_client.post(
        "/api/v1/rating-tables",
        {"code": "EMPTY", "name": "Empty", "effectiveFrom": "2026-01-01", "factors": []},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_publish_rating_table_is_immutable(admin_client):
    created = admin_client.post(
        "/api/v1/rating-tables",
        {"code": "PUB", "name": "Pub", "effectiveFrom": "2026-01-01", "factors": _factors_payload()},
        format="json",
    ).data

    published = admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")
    assert published.status_code == 200
    assert published.data["status"] == "PUBLISHED"

    republish = admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")
    assert republish.status_code == 409
    assert republish.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_second_version_increments(admin_client):
    admin_client.post(
        "/api/v1/rating-tables",
        {"code": "SEQ", "name": "Seq", "effectiveFrom": "2026-01-01", "factors": _factors_payload()},
        format="json",
    )
    second = admin_client.post(
        "/api/v1/rating-tables",
        {"code": "SEQ", "name": "Seq v2", "effectiveFrom": "2026-06-01", "factors": _factors_payload()},
        format="json",
    ).data
    assert second["versionNo"] == 2


@pytest.mark.django_db
def test_resolve_factor_picks_most_specific_match(tenant, admin_client):
    import datetime

    created = admin_client.post(
        "/api/v1/rating-tables",
        {"code": "RESOLVE", "name": "Resolve", "effectiveFrom": "2026-01-01", "factors": _factors_payload()},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")

    actor = Actor(actor_id="tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    try:
        rating_table = resolve_rating_table(code="RESOLVE", effective_date=datetime.date(2026, 6, 1))
        assert rating_table is not None
        assert rating_table.status == "PUBLISHED"

        exact = resolve_factor(rating_table=rating_table, factor_code="AGE_FACTOR", context={"ageBand": "70+"})
        assert exact is not None
        assert exact.factor_value == Decimal("3.80")

        fallback = resolve_factor(
            rating_table=rating_table, factor_code="AGE_FACTOR", context={"ageBand": "unknown-band"}
        )
        assert fallback is not None
        assert fallback.factor_value == Decimal("1.00")
        assert fallback.dimension_json == {}
    finally:
        CurrentActorProvider.reset(token)


@pytest.mark.django_db
def test_resolve_rating_table_ignores_draft(tenant, admin_client):
    import datetime

    admin_client.post(
        "/api/v1/rating-tables",
        {"code": "DRAFTONLY", "name": "Draft", "effectiveFrom": "2026-01-01", "factors": _factors_payload()},
        format="json",
    )

    actor = Actor(actor_id="tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    try:
        assert resolve_rating_table(code="DRAFTONLY", effective_date=datetime.date(2026, 6, 1)) is None
    finally:
        CurrentActorProvider.reset(token)
