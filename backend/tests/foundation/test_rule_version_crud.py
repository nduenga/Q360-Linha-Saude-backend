"""ROADMAP_ANGOLA_CUSTOMIZATION.md Epico 6: PATCH/DELETE for a DRAFT
RuleVersion, rejection once PUBLISHED, and retire as the safe way to take
a PUBLISHED one out of use."""
from __future__ import annotations

import pytest


def _create(admin_client, code: str) -> dict:
    return admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": code,
            "name": "Original",
            "ruleDomain": "ELIGIBILITY",
            "effectiveFrom": "2026-01-01",
            "artifactType": "INTERNAL",
        },
        format="json",
    ).data


@pytest.mark.django_db
def test_patch_draft_rule_version_updates_name_and_artifact(admin_client, tenant):
    created = _create(admin_client, "CRUD-RV-1")

    response = admin_client.patch(
        f"/api/v1/rule-versions/{created['id']}",
        {"name": "Renamed", "artifactType": "JSON", "artifactRef": "s3://rules/renamed.json"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "DRAFT"

    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.permissions import Role
    from apps.foundation.domain.tenant import TenantId
    from apps.foundation.infrastructure.models import RuleVersion

    actor = Actor(actor_id="tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    try:
        updated = RuleVersion.objects.select_related("rule_set").get(id=created["id"])
        assert updated.artifact_type == "JSON"
        assert updated.artifact_ref == "s3://rules/renamed.json"
        assert updated.rule_set.name == "Renamed"
    finally:
        CurrentActorProvider.reset(token)


@pytest.mark.django_db
def test_delete_draft_rule_version_removes_it(admin_client):
    created = _create(admin_client, "CRUD-RV-2")

    response = admin_client.delete(f"/api/v1/rule-versions/{created['id']}")
    assert response.status_code == 204

    listing = admin_client.get("/api/v1/rule-versions")
    assert all(item["id"] != created["id"] for item in listing.data["items"])


@pytest.mark.django_db
def test_patch_published_rule_version_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-RV-3")
    admin_client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")

    response = admin_client.patch(
        f"/api/v1/rule-versions/{created['id']}",
        {"name": "Should Fail", "artifactType": "INTERNAL"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_delete_published_rule_version_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-RV-4")
    admin_client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")

    response = admin_client.delete(f"/api/v1/rule-versions/{created['id']}")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_retire_published_rule_version_marks_it_retired(admin_client):
    created = _create(admin_client, "CRUD-RV-5")
    admin_client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")

    response = admin_client.post(f"/api/v1/configuration/rule-version/{created['id']}/retire")
    assert response.status_code == 200
    assert response.data["status"] == "RETIRED"


@pytest.mark.django_db
def test_retire_draft_rule_version_is_rejected(admin_client):
    created = _create(admin_client, "CRUD-RV-6")

    response = admin_client.post(f"/api/v1/configuration/rule-version/{created['id']}/retire")
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"
