"""Integration tests for POST /api/v1/eligibility/evaluate against a real
Postgres — exercises the full chain: product/plan (S2) + proposer/member
(S3) + rule-version (foundation) + eligibility evaluation (S3), matching
Q360-S3-03 acceptance criteria: "Hard stop bloqueia • Warning permite
continuar • Referral encaminha • Config error impede".
"""
from __future__ import annotations

import json

import pytest


def _setup_product_plan(client) -> dict:
    product = client.post("/api/v1/products", {"code": "ELIG-PROD", "name": "Eligibility Product"}).data
    version = client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    ).data
    # Plans can only be added to a DRAFT version (Q360-S2 immutability
    # invariant) — must create the plan BEFORE publishing the version.
    plan = client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "PLAN-A", "name": "Plan A"}
    ).data
    client.post(f"/api/v1/product-versions/{version['id']}/publish")
    return {"productVersionId": version["id"], "planId": plan["id"]}


def _setup_member(client, *, date_of_birth: str, relationship_code: str = "TITULAR") -> dict:
    proposer = client.post("/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "P"}).data
    member = client.post(
        "/api/v1/members",
        {"proposerId": proposer["id"], "relationshipCode": relationship_code, "dateOfBirth": date_of_birth},
    ).data
    return {"proposerId": proposer["id"], "memberId": member["id"]}


def _publish_eligibility_rules(client, config: dict) -> None:
    created = client.post(
        "/api/v1/rule-versions",
        {
            "code": "ELIG-DEFAULT",
            "name": "Default eligibility rules",
            "ruleDomain": "ELIGIBILITY",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": json.dumps(config),
        },
        format="json",
    ).data
    publish = client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")
    assert publish.status_code == 200, publish.data


@pytest.mark.django_db
def test_config_error_when_no_rule_version_published(admin_client):
    scope = _setup_product_plan(admin_client)
    who = _setup_member(admin_client, date_of_birth="1990-01-01")

    response = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {**scope, **who, "effectiveDate": "2026-06-01", "context": {}},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["decision"] == "CONFIG_ERROR"
    assert response.data["messages"][0]["code"] == "ELIG-RULE-MISSING"
    assert response.data["ruleVersionId"] is None


@pytest.mark.django_db
def test_eligible_when_within_configured_bounds(admin_client):
    _publish_eligibility_rules(admin_client, {"minEntryAge": 18, "maxEntryAge": 65})
    scope = _setup_product_plan(admin_client)
    who = _setup_member(admin_client, date_of_birth="1990-01-01")

    response = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {**scope, **who, "effectiveDate": "2026-06-01", "context": {}},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["decision"] == "ELIGIBLE"
    assert response.data["ruleVersionId"] is not None


@pytest.mark.django_db
def test_hard_stop_below_minimum_age(admin_client):
    _publish_eligibility_rules(admin_client, {"minEntryAge": 18})
    scope = _setup_product_plan(admin_client)
    who = _setup_member(admin_client, date_of_birth="2020-01-01")  # ~6 years old

    response = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {**scope, **who, "effectiveDate": "2026-06-01", "context": {}},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["decision"] == "HARD_STOP"
    assert response.data["messages"][0]["code"] == "ELIG-AGE-MIN"


@pytest.mark.django_db
def test_referral_when_criteria_matched(admin_client):
    _publish_eligibility_rules(admin_client, {"referralCriteria": [{"minAge": 70}]})
    scope = _setup_product_plan(admin_client)
    who = _setup_member(admin_client, date_of_birth="1950-01-01")

    response = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {**scope, **who, "effectiveDate": "2026-06-01", "context": {}},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["decision"] == "REFERRAL"


@pytest.mark.django_db
def test_warning_when_criteria_matched(admin_client):
    _publish_eligibility_rules(admin_client, {"warningCriteria": [{"relationshipCodes": ["FILHO"]}]})
    scope = _setup_product_plan(admin_client)
    who = _setup_member(admin_client, date_of_birth="2010-01-01", relationship_code="FILHO")

    response = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {**scope, **who, "effectiveDate": "2026-06-01", "context": {}},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["decision"] == "WARNING"


@pytest.mark.django_db
def test_hard_stop_plan_inactive_short_circuits_before_rules(admin_client):
    # No rule-version published at all — proves ELIG-007 is checked before
    # ELIG-010, i.e. an inactive plan never depends on rule configuration.
    scope = _setup_product_plan(admin_client)
    from apps.product.infrastructure.models import Plan

    # `all_tenants` (not `objects`): this test helper runs outside any
    # authenticated request, so no CurrentTenantProvider context is bound.
    Plan.all_tenants.filter(id=scope["planId"]).update(status="INACTIVE")
    who = _setup_member(admin_client, date_of_birth="1990-01-01")

    response = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {**scope, **who, "effectiveDate": "2026-06-01", "context": {}},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["decision"] == "HARD_STOP"
    assert response.data["messages"][0]["code"] == "ELIG-PLAN-INACTIVE"


@pytest.mark.django_db
def test_missing_required_fields_is_400():
    from tests.eligibility.conftest import make_client
    import uuid

    client = make_client(tenant_id=uuid.uuid4(), roles=["ADMIN"], scope="q360.write")
    response = client.post(
        "/api/v1/eligibility/evaluate",
        {"effectiveDate": "2026-06-01", "context": {}},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_unknown_product_version_is_400_not_500(admin_client):
    plan_scope = _setup_product_plan(admin_client)
    who = _setup_member(admin_client, date_of_birth="1990-01-01")

    response = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {
            "productVersionId": "11111111-1111-1111-1111-111111111111",
            "planId": plan_scope["planId"],
            **who,
            "effectiveDate": "2026-06-01",
            "context": {},
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_list_rule_versions_filters_by_domain(admin_client):
    """Pragmatic V1 addition (OPEN_DECISIONS.md#S04-LISTING-GAPS-001):
    ART-006 has no listRuleVersions."""
    admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": "LIST-ELIG",
            "name": "List Elig",
            "ruleDomain": "ELIGIBILITY",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": "{}",
        },
        format="json",
    )
    admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": "LIST-PRICE",
            "name": "List Price",
            "ruleDomain": "PRICING",
            "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": "{}",
        },
        format="json",
    )

    response = admin_client.get("/api/v1/rule-versions?ruleDomain=PRICING")
    assert response.status_code == 200
    codes = [item["code"] for item in response.data["items"]]
    assert "LIST-PRICE" in codes
    assert "LIST-ELIG" not in codes
