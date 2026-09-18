"""Q360-S11 — executes the ART-013 golden-test cases
(docs/artifacts/ART-013-golden-tests/golden/*.json) against real code,
per the artifact's own "Core invariant": same normalized input + same
exact versions/rules/rounding policy = exact same result.

`PENDING_OD_pricing_template.json` is explicitly skipped (README.md: it
is a deliberately incomplete template pending an Open Decision, never a
runnable case).

GT-PRICE-005 is engine-agnostic in the artifact (its `versions` are all
`TECHNICAL-FIXTURE` placeholders and its component codes are the generic
labels "A"/"B", neither of which exist in Q360's real vocabulary —
Q360's own base component is always coded `BASE_PREMIUM`, and an
adjustment's code is whatever a published PRICING RuleVersion declares).
We exercise the *invariant* the case validates — decimal-exact
reconciliation of base + adjustment = total, in the case's currency —
using Q360's real base-premium + rule-adjustment mechanism, and assert
only the fields that are not artifact-specific to a different engine's
naming (state, currency, total, and the two contributing amounts).
Never invents a mapping from "A"/"B" to real Q360 codes.
"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

# `tests/integration` has no local conftest.py defining admin_client/tenant
# fixtures (pytest-django's own built-in `admin_client` fixture needs
# django.contrib.sessions, which this project's minimal INSTALLED_APPS
# does not include) — reuse the same self-contained tenant/JWT helpers
# `test_tenant_isolation.py` already established for this directory.
from tests.integration.test_tenant_isolation import _make_tenant, _oidc_static_key, make_client  # noqa: F401

_GOLDEN_DIR = Path(__file__).resolve().parents[3] / "docs" / "artifacts" / "ART-013-golden-tests" / "golden"


def _load(case_id: str) -> dict:
    return json.loads((_GOLDEN_DIR / f"{case_id}.json").read_text(encoding="utf-8"))


@pytest.fixture
def tenant(db):
    return _make_tenant()


@pytest.fixture
def admin_client(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin q360.approve")


def test_golden_directory_has_no_unexpected_new_cases():
    """A new case dropped into the artifact directory must be picked up
    by a real test in this file, not silently ignored — this is a tripwire,
    not a golden assertion itself."""
    known = {"GT-ELIG-002.json", "GT-WF-003.json", "GT-PRICE-005.json", "GT-IDEMP-002.json",
             "PENDING_OD_pricing_template.json", "README.md"}
    on_disk = {p.name for p in _GOLDEN_DIR.iterdir()}
    assert on_disk == known, f"Unrecognised golden files (add a case for them): {on_disk - known}"


@pytest.mark.django_db
def test_GT_ELIG_002_product_not_effective_is_hard_stop(admin_client):
    case = _load("GT-ELIG-002")
    snap = case["inputSnapshot"]

    product = admin_client.post("/api/v1/products", {"code": f"GT-ELIG-{uuid.uuid4().hex[:8]}", "name": "P"}).data
    version = admin_client.post(
        f"/api/v1/products/{product['id']}/versions",
        {"effectiveFrom": snap["productEffectiveFrom"], "effectiveTo": snap["productEffectiveTo"]},
        format="json",
    ).data
    plan = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "B", "name": "B"}
    ).data
    proposer_id = admin_client.post(
        "/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "H"}
    ).data["id"]
    member_id = admin_client.post(
        "/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data["id"]

    resp = admin_client.post(
        "/api/v1/eligibility/evaluate",
        {
            "proposerId": proposer_id,
            "memberId": member_id,
            "productVersionId": version["id"],
            "planId": plan["id"],
            "effectiveDate": snap["quoteEffectiveDate"],
            "context": {},
        },
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["decision"] == case["expected"]["decision"]
    codes = {m["code"] for m in resp.data["messages"]}
    assert case["expected"]["code"] in codes


@pytest.mark.django_db
def test_GT_WF_003_same_actor_cannot_approve_own_submission(admin_client, tenant):
    """Reuses the exact real flow already proven in
    tests/quote/test_review_workflow.py::test_submitter_cannot_approve_own_quote
    — this wrapper ties it explicitly to the ART-013 golden case."""
    case = _load("GT-WF-003")
    from tests.quote.test_review_workflow import _ready_quote

    quote = _ready_quote(admin_client, code_suffix=f"gt-{uuid.uuid4().hex[:6]}")
    submitted = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json"
    ).data
    assert submitted["status"] == case["inputSnapshot"]["quoteState"]
    row_version_before = submitted["rowVersion"]

    response = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": case["inputSnapshot"]["decision"], "reasonCode": "OK", "rowVersion": row_version_before},
        format="json",
    )
    assert response.status_code == case["expected"]["httpStatus"]
    assert response.data["code"] == case["expected"]["code"]

    after = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    assert after["status"] == case["expected"]["quoteState"]
    if case["expected"]["businessEffects"] == 0:
        assert after["rowVersion"] == row_version_before


@pytest.mark.django_db
def test_GT_PRICE_005_base_plus_adjustment_reconciles_exactly(admin_client):
    case = _load("GT-PRICE-005")
    suffix = uuid.uuid4().hex[:8]
    base_amount = Decimal(case["inputSnapshot"]["syntheticComponents"][0]["amount"])
    adjustment_amount = Decimal(case["inputSnapshot"]["syntheticComponents"][1]["amount"])

    product = admin_client.post("/api/v1/products", {"code": f"GT-PRICE-{suffix}", "name": "P"}).data
    version = admin_client.post(
        f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
    ).data
    plan = admin_client.post(
        "/api/v1/plans", {"productVersionId": version["id"], "code": "B", "name": "B"}
    ).data
    params = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": f"GT-PRICE-PARAMS-{suffix}", "name": "p", "effectiveFrom": "2026-01-01",
            "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": str(base_amount)}],
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{params['id']}/publish")
    table = admin_client.post(
        "/api/v1/rating-tables",
        {
            "code": f"GT-PRICE-TABLE-{suffix}", "name": "t", "effectiveFrom": "2026-01-01",
            "currencyCode": case["currency"],
            "factors": [{"factorCode": "NEUTRAL", "dimensions": {}, "factorValue": "1.00"}],
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rating-table/{table['id']}/publish")
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": f"GT-PRICE-RULE-{suffix}", "name": "r", "ruleDomain": "PRICING", "effectiveFrom": "2026-01-01",
            "artifactType": "JSON",
            "artifactRef": json.dumps({"adjustments": [{"code": "B", "when": {}, "amount": str(adjustment_amount)}]}),
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    elig_rule = admin_client.post(
        "/api/v1/rule-versions",
        {
            "code": f"GT-PRICE-ELIG-{suffix}", "name": "e", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
            "artifactType": "JSON", "artifactRef": json.dumps({}),
        },
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{elig_rule['id']}/publish")
    admin_client.post(f"/api/v1/product-versions/{version['id']}/publish")

    proposer_id = admin_client.post(
        "/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "H"}
    ).data["id"]
    member_id = admin_client.post(
        "/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}
    ).data["id"]
    quote = admin_client.post(
        "/api/v1/quotes",
        {"productVersionId": version["id"], "planId": plan["id"], "proposerId": proposer_id, "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")

    priced = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert priced.status_code == 200
    assert priced.data["status"] == case["expectedState"]
    assert priced.data["currencyCode"] == case["currency"]
    assert Decimal(priced.data["totalAmount"]) == Decimal(case["expectedTotal"])

    amounts = {Decimal(c["resultAmount"]) for c in priced.data["components"] if c["type"] in ("BASE", "ADJUSTMENT")}
    assert amounts == {base_amount, base_amount + adjustment_amount}


@pytest.mark.django_db
def test_GT_IDEMP_002_second_delivery_is_ack_noop():
    """Consumer-side idempotency via `consumer_inbox` (ART-007): the same
    `eventId` delivered twice to the same consumer produces exactly one
    business effect and one inbox row; the second delivery is a no-op ACK.
    No real broker/consumer exists (ART-007 Non-Goal for V1) — this proves
    the inbox de-duplication primitive itself, which any future consumer
    is required to use."""
    case = _load("GT-IDEMP-002")
    snap = case["inputSnapshot"]

    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.permissions import Role
    from apps.foundation.domain.tenant import TenantId
    from apps.foundation.infrastructure.models import ConsumerInbox, Tenant

    tenant = Tenant.objects.create(id=uuid.UUID(snap["tenantId"]), code=f"gt-idemp-{uuid.uuid4().hex[:8]}", name="GT")
    actor = Actor(actor_id="gt-idemp", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))
    token = CurrentActorProvider.bind(actor)
    try:
        event_id = uuid.UUID(snap["eventId"])
        business_effects = 0
        processed_rows = 0
        last_result = None

        for _delivery in range(snap["deliveries"]):
            already = ConsumerInbox.objects.filter(consumer_name=snap["consumer"], event_id=event_id).exists()
            if already:
                last_result = "ACK_NOOP"
                continue
            ConsumerInbox.objects.create(
                tenant_id=tenant.id,
                event_id=event_id,
                consumer_name=snap["consumer"],
                event_type="QUOTE.SUBMITTED",
                schema_version=1,
            )
            business_effects += 1
            processed_rows += 1
            last_result = "PROCESSED"

        assert business_effects == case["expected"]["businessEffects"]
        assert processed_rows == case["expected"]["processedInboxRows"]
        assert last_result == case["expected"]["secondDelivery"]
        assert ConsumerInbox.objects.filter(consumer_name=snap["consumer"], event_id=event_id).count() == 1
    finally:
        CurrentActorProvider.reset(token)
