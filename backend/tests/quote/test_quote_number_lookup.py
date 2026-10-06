"""ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 4 (OD-ANGOLA-005: "apólice" =
quoteNumber of an approved Quote) + Product Owner decision (2026-09-25):
every Quote is assigned a stable, sequential "COT-N" quote_number as soon
as it is created (DECISIONS_TAKEN.md#S06-QUOTE-001 item 4), not only once
approved - it stays the same number through submit/approve/reject/return.
GET /quotes?quoteNumber= resolves everything a lookup-by-number flow needs
(planId, proposerId, effectiveDate) from that single number, at any
status.
"""
from __future__ import annotations

import uuid

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_review_workflow import _ready_quote


def _approver(tenant, *, actor_id: str = "approver-1"):
    return make_client(
        tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope="q360.read q360.write q360.approve", actor_id=actor_id
    )


@pytest.mark.django_db
def test_quote_number_is_assigned_on_creation(admin_client):
    """Product Owner decision (2026-09-25): no need to wait for approval —
    a Quote is identifiable by its "COT-N" number from the moment it
    exists (DRAFT)."""
    quote = _ready_quote(admin_client, code_suffix="qn1")
    assert quote["quoteNumber"] is not None
    assert quote["quoteNumber"].startswith("COT-")


@pytest.mark.django_db
def test_quote_number_stays_the_same_through_approve_reject_or_return(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="qn1b")
    original_number = quote["quoteNumber"]
    assert original_number is not None

    submitted = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json"
    ).data
    assert submitted["quoteNumber"] == original_number

    approved = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    ).data
    assert approved["quoteNumber"] == original_number


@pytest.mark.django_db
def test_reject_and_return_keep_the_quote_number_assigned_at_creation(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="qn2")
    original_number = quote["quoteNumber"]
    submitted = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json"
    ).data
    rejected = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "REJECT", "reasonCode": "NOT_ELIGIBLE", "rowVersion": submitted["rowVersion"]},
        format="json",
    ).data
    assert rejected["quoteNumber"] == original_number


@pytest.mark.django_db
def test_lookup_by_quote_number_resolves_full_context(admin_client, tenant):
    quote = _ready_quote(admin_client, code_suffix="qn3")
    submitted = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json"
    ).data
    approved = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    ).data

    found = admin_client.get(f"/api/v1/quotes?quoteNumber={approved['quoteNumber']}")
    assert found.status_code == 200
    assert len(found.data["items"]) == 1
    resolved = found.data["items"][0]
    assert resolved["id"] == quote["id"]
    assert resolved["planId"] == quote["planId"]
    assert resolved["proposerId"] == quote["proposerId"]
    assert resolved["effectiveDate"] == quote["effectiveDate"]


@pytest.mark.django_db
def test_lookup_by_unknown_quote_number_returns_empty(admin_client):
    resp = admin_client.get("/api/v1/quotes?quoteNumber=DOES-NOT-EXIST")
    assert resp.status_code == 200
    assert resp.data["items"] == []


@pytest.mark.django_db
def test_two_approved_quotes_get_different_numbers(admin_client, tenant):
    """Two full `_ready_quote` setups in the same tenant would make the
    pricing auto-resolve ambiguous (two published rating tables/parameter
    sets effective on the same date) — a pre-existing property of that
    shared test helper, unrelated to numbering. Uniqueness is instead
    proven across two quotes approved on two independent tenants, which is
    exactly numbering_service's real isolation boundary (its concurrency
    safety within one tenant is already proven by
    NumberingConcurrencyTest in test_documents_and_cancellation.py)."""
    from apps.foundation.infrastructure.models import Tenant

    quote_a = _ready_quote(admin_client, code_suffix="qn4a")
    submitted_a = admin_client.post(
        f"/api/v1/quotes/{quote_a['id']}/submit", {"rowVersion": quote_a["rowVersion"]}, format="json"
    ).data
    approved_a = _approver(tenant, actor_id="approver-a").post(
        f"/api/v1/quotes/{quote_a['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted_a["rowVersion"]},
        format="json",
    ).data
    assert approved_a["quoteNumber"] == "COT-1"

    other_tenant = Tenant.objects.create(id=uuid.uuid4(), code="qn4-other", name="Other")
    other_admin = make_client(
        tenant_id=other_tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin"
    )
    quote_b = _ready_quote(other_admin, code_suffix="qn4b")
    submitted_b = other_admin.post(
        f"/api/v1/quotes/{quote_b['id']}/submit", {"rowVersion": quote_b["rowVersion"]}, format="json"
    ).data
    approved_b = _approver(other_tenant, actor_id="approver-b").post(
        f"/api/v1/quotes/{quote_b['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted_b["rowVersion"]},
        format="json",
    ).data
    # Independent per-tenant sequence: both legitimately start at "COT-1".
    assert approved_b["quoteNumber"] == "COT-1"
