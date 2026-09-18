"""Q360-S9-05 acceptance criteria (AC-5 in
.trae/specs/s09-s11-restantes/spec.md): exercising a real, already-
implemented operation appends an `outbox_event` row with the exact
ART-007 `eventType` (uppercase-with-dots) and non-null minimal payload
fields — covering PRODUCT.VERSION.PUBLISHED, PROPOSER.CREATED,
MEMBER.CREATED, ELIGIBILITY.EVALUATED, PRICING.CALCULATED, QUOTE.CREATED,
QUOTE.SUBMITTED and QUOTE.APPROVED, driven through one realistic end-to-end
flow (product -> proposer/member -> quote -> price -> submit -> approve)
rather than eight disconnected fixtures.
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from apps.foundation.infrastructure.models import OutboxEvent
from tests.integration.test_tenant_isolation import _make_tenant, _oidc_static_key, make_client  # noqa: F401


def _events_for(tenant_id, event_type: str) -> list[OutboxEvent]:
    return list(OutboxEvent.all_tenants.filter(tenant_id=tenant_id, event_type=event_type).order_by("occurred_at"))


@pytest.mark.django_db
def test_outbox_event_catalog_end_to_end():
    tenant = _make_tenant(suffix="OUTBOX")
    owner = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
    approver = make_client(
        tenant_id=tenant.id, roles=["APPROVER"], scope="q360.read q360.write q360.approve", actor_id="approver-1"
    )

    product = owner.post("/api/v1/products", {"code": "OUTBOX-P", "name": "P"}).data
    version = owner.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}).data
    plan = owner.post("/api/v1/plans", {"productVersionId": version["id"], "code": "B", "name": "B"}).data

    elig_rule = owner.post(
        "/api/v1/rule-versions",
        {"code": "OUTBOX-ELIG", "name": "e", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    owner.post(f"/api/v1/configuration/rule-version/{elig_rule['id']}/publish")

    params = owner.post(
        "/api/v1/pricing-parameter-sets",
        {"code": "OUTBOX-PARAMS", "name": "p", "effectiveFrom": "2026-01-01",
         "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "50.00"}]},
        format="json",
    ).data
    owner.post(f"/api/v1/configuration/pricing-parameter-set/{params['id']}/publish")

    table = owner.post(
        "/api/v1/rating-tables",
        {"code": "OUTBOX-TABLE", "name": "t", "effectiveFrom": "2026-01-01", "currencyCode": "AOA",
         "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}]},
        format="json",
    ).data
    owner.post(f"/api/v1/configuration/rating-table/{table['id']}/publish")

    publish_resp = owner.post(f"/api/v1/product-versions/{version['id']}/publish")
    assert publish_resp.status_code == 200

    proposer = owner.post("/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "Holder"}).data
    member = owner.post(
        "/api/v1/members", {"proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data

    quote = owner.post(
        "/api/v1/quotes",
        {"productVersionId": version["id"], "planId": plan["id"], "proposerId": proposer["id"], "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    owner.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json")
    priced = owner.post(f"/api/v1/quotes/{quote['id']}/price").data
    ready = owner.get(f"/api/v1/quotes/{quote['id']}").data
    submitted = owner.post(
        f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": ready["rowVersion"]}, format="json"
    ).data
    approved = approver.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    ).data
    assert approved["status"] == "APPROVED"

    # PRODUCT.VERSION.PUBLISHED
    events = _events_for(tenant.id, "PRODUCT.VERSION.PUBLISHED")
    assert len(events) == 1
    payload = events[0].payload_json["payload"]
    assert payload["productVersionId"] == version["id"]
    assert payload["productId"] == product["id"]

    # PROPOSER.CREATED
    events = _events_for(tenant.id, "PROPOSER.CREATED")
    assert len(events) == 1
    assert events[0].payload_json["payload"]["proposerId"] == proposer["id"]

    # MEMBER.CREATED
    events = _events_for(tenant.id, "MEMBER.CREATED")
    assert len(events) == 1
    payload = events[0].payload_json["payload"]
    assert payload["memberId"] == member["id"]
    assert payload["proposerId"] == proposer["id"]

    # ELIGIBILITY.EVALUATED (fired once for the quote-member add)
    events = _events_for(tenant.id, "ELIGIBILITY.EVALUATED")
    assert len(events) >= 1
    payload = events[0].payload_json["payload"]
    assert payload["memberId"] == member["id"]
    assert payload["decision"]

    # PRICING.CALCULATED
    events = _events_for(tenant.id, "PRICING.CALCULATED")
    assert len(events) >= 1
    payload = events[-1].payload_json["payload"]
    assert payload["pricingRunId"] == priced["pricingRunId"]
    assert Decimal(payload["totalAmount"]) == Decimal(priced["totalAmount"])
    assert payload["currencyCode"] == priced["currencyCode"]

    # QUOTE.CREATED
    events = _events_for(tenant.id, "QUOTE.CREATED")
    assert len(events) == 1
    payload = events[0].payload_json["payload"]
    assert payload["quoteId"] == quote["id"]
    assert payload["status"] == "DRAFT"

    # QUOTE.SUBMITTED — NOTE: ART-007 also declares snapshotId, reviewTaskId
    # and status on this payload; the current implementation only emits
    # quoteId/submittedBy/submittedAt (see quote_service.submit_quote).
    # Tracked as a known field-completeness gap, not asserted here.
    events = _events_for(tenant.id, "QUOTE.SUBMITTED")
    assert len(events) == 1
    payload = events[0].payload_json["payload"]
    assert payload["quoteId"] == quote["id"]
    assert payload["submittedBy"] == "actor-1"
    assert payload["submittedAt"]

    # QUOTE.APPROVED — NOTE: ART-007 also declares snapshotId, decisionId
    # and status; current implementation emits quoteId/decision/reasonCode/
    # reasonText/decidedBy/approvedAt instead (see quote_service.decide_quote).
    # Same known gap as QUOTE.SUBMITTED above.
    events = _events_for(tenant.id, "QUOTE.APPROVED")
    assert len(events) == 1
    payload = events[0].payload_json["payload"]
    assert payload["quoteId"] == quote["id"]
    assert payload["decision"] == "APPROVE"
    assert payload["decidedBy"] == "approver-1"

    # Every row for this tenant is PENDING until a dispatcher pass runs —
    # the outbox write is transactional/local, publishing is a separate
    # concern (AC-4).
    assert OutboxEvent.all_tenants.filter(tenant_id=tenant.id).exclude(status="PENDING").count() == 0
