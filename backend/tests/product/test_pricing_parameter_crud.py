"""ROADMAP_ANGOLA_CUSTOMIZATION.md Epico 6: PATCH/DELETE for a DRAFT
PricingParameterSet, rejection once PUBLISHED, and retire as the safe way
to take a PUBLISHED one out of use."""
from __future__ import annotations

import pytest


def _create(admin_client, code: str) -> dict:
    return admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": code, "effectiveFrom": "2026-01-01", "parameters": [{"code": "X", "valueType": "INTEGER", "value": 1}]},
        format="json",
    ).data


@pytest.mark.django_db
def test_patch_draft_parameter_set_replaces_parameters(admin_client, tenant):
    created = _create(admin_client, "CRUD-PS-1")

    response = admin_client.patch(
        f"/api/v1/pricing-parameter-sets/{created['id']}",
        {"parameters": [{"code": "Y", "valueType": "DECIMAL", "value": "9.90"}]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "DRAFT"

    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.permissions import Role
    from apps.foundation.domain.tenant import TenantId
    from apps.product.infrastructure.models import PricingParameter

    actor = Actor(actor_id="tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    try:
        codes = list(
            PricingParameter.objects.filter(parameter_set_id=created["id"]).values_list("parameter_code", flat=True)
        )
        assert codes == ["Y"]
    finally:
        CurrentActorProvider.reset(token)


@pytest.mark.django_db
def test_delete_draft_parameter_set_removes_it(admin_client):
    created = _create(admin_client, "CRUD-PS-2")

    response = admin_client.delete(f"/api/v1/pricing-parameter-sets/{created['id']}")
    assert response.status_code == 204

    listing = admin_client.get("/api/v1/pricing-parameter-sets")
    assert all(item["id"] != created["id"] for item in listing.data["items"])


@pytest.mark.django_db
def test_patch_published_parameter_set_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-PS-3")
    admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")

    response = admin_client.patch(
        f"/api/v1/pricing-parameter-sets/{created['id']}",
        {"parameters": [{"code": "Y", "valueType": "INTEGER", "value": 2}]},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_delete_published_parameter_set_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-PS-4")
    admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")

    response = admin_client.delete(f"/api/v1/pricing-parameter-sets/{created['id']}")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_retire_published_parameter_set_marks_it_retired(admin_client):
    created = _create(admin_client, "CRUD-PS-5")
    admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")

    response = admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/retire")
    assert response.status_code == 200
    assert response.data["status"] == "RETIRED"


@pytest.mark.django_db
def test_retire_draft_parameter_set_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-PS-6")

    response = admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/retire")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"
