"""Q360-S8-01..03 acceptance criteria: "Documento reflecte snapshot •
Template version identificado • Reprodução possível" (S8-01), "Sem
duplicação em concorrência" (S8-02), "Só transições autorizadas • Motivo
registado" (S8-03)."""
from __future__ import annotations

import json
import threading

import pytest
from django.test import TransactionTestCase

from tests.quote.conftest import make_client


def _plan(client, *, product_code: str) -> dict:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    version = client.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}).data
    plan = client.post("/api/v1/plans", {"productVersionId": version["id"], "code": "BASIC", "name": "Basic"}).data
    client.post(f"/api/v1/product-versions/{version['id']}/publish")
    return {"productVersionId": version["id"], "planId": plan["id"]}


def _approved_quote(client, *, code_suffix: str, tenant) -> dict:
    """Full setup ending with an APPROVED quote (S6/S7 already proven)."""
    plan_ref = _plan(client, product_code=f"DOC-PROD-{code_suffix}")
    client.post(
        "/api/v1/pricing-parameter-sets",
        {"code": f"DOC-PARAMS-{code_suffix}", "effectiveFrom": "2026-01-01", "parameters": [{"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "100.00"}]},
        format="json",
    )
    parameter_set_created = client.get("/api/v1/pricing-parameter-sets").data["items"]
    for p in parameter_set_created:
        if p["code"] == f"DOC-PARAMS-{code_suffix}":
            client.post(f"/api/v1/configuration/pricing-parameter-set/{p['id']}/publish")
    table = client.post(
        "/api/v1/rating-tables",
        {"code": f"DOC-TABLE-{code_suffix}", "name": "t", "effectiveFrom": "2026-01-01", "currencyCode": "AOA", "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}]},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rating-table/{table['id']}/publish")
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": f"DOC-ELIG-{code_suffix}", "name": "e", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01", "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")

    proposer_id = client.post("/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "Holder"}).data["id"]
    member_id = client.post("/api/v1/members", {"proposerId": proposer_id, "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01"}).data["id"]
    quote = client.post("/api/v1/quotes", {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"}, format="json").data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    client.post(f"/api/v1/quotes/{quote['id']}/price")
    ready = client.get(f"/api/v1/quotes/{quote['id']}").data
    submitted = client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": ready["rowVersion"]}, format="json").data

    approver = make_client(tenant_id=tenant.id, roles=["APPROVER"], scope="q360.read q360.write q360.approve", actor_id=f"approver-{code_suffix}")
    approver.post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]},
        format="json",
    )
    return client.get(f"/api/v1/quotes/{quote['id']}").data


def _publish_default_template(client, *, code_suffix: str) -> None:
    from apps.quote.application.document_service import DEFAULT_TEMPLATE_CODE

    created = client.post(
        "/api/v1/document-templates",
        {"templateCode": DEFAULT_TEMPLATE_CODE, "storageRef": f"internal://placeholder-{code_suffix}", "effectiveFrom": "2026-01-01"},
        format="json",
    ).data
    client.post(f"/api/v1/document-templates/{created['id']}/publish")


@pytest.mark.django_db
def test_generate_proposal_without_template_is_not_found(admin_client, tenant):
    quote = _approved_quote(admin_client, code_suffix="1", tenant=tenant)
    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/proposal")
    assert response.status_code == 404
    assert response.data["code"] == "NOT-FOUND"


@pytest.mark.django_db
def test_generate_proposal_before_approved_is_quote_state_error(admin_client):
    plan_ref = _plan(admin_client, product_code="DOC-PROD-2")
    proposer_id = admin_client.post("/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "H"}).data["id"]
    quote = admin_client.post("/api/v1/quotes", {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"}, format="json").data
    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/proposal")
    assert response.status_code == 409
    assert response.data["code"] == "QUOTE-STATE"


@pytest.mark.django_db
def test_generate_proposal_full_flow(admin_client, tenant):
    quote = _approved_quote(admin_client, code_suffix="3", tenant=tenant)
    _publish_default_template(admin_client, code_suffix="3")

    generated = admin_client.post(f"/api/v1/quotes/{quote['id']}/proposal")
    assert generated.status_code == 202
    assert generated.data["status"] == "GENERATED"
    assert generated.data["documentNumber"] is not None
    assert generated.data["documentType"] == "QUOTE_PROPOSAL"

    fetched = admin_client.get(f"/api/v1/quotes/{quote['id']}/proposal")
    assert fetched.status_code == 200
    assert fetched.data["id"] == generated.data["id"]


@pytest.mark.django_db
def test_list_document_templates(admin_client):
    _publish_default_template(admin_client, code_suffix="list-1")
    resp = admin_client.get("/api/v1/document-templates")
    assert resp.status_code == 200
    from apps.quote.application.document_service import DEFAULT_TEMPLATE_CODE

    codes = {item["templateCode"] for item in resp.data["items"]}
    assert DEFAULT_TEMPLATE_CODE in codes

    filtered = admin_client.get(f"/api/v1/document-templates?templateCode={DEFAULT_TEMPLATE_CODE}")
    assert filtered.status_code == 200
    assert all(item["templateCode"] == DEFAULT_TEMPLATE_CODE for item in filtered.data["items"])


@pytest.mark.django_db
def test_cancel_draft_quote_requires_reason(admin_client):
    plan_ref = _plan(admin_client, product_code="DOC-PROD-4")
    proposer_id = admin_client.post("/api/v1/proposers", {"proposerType": "INDIVIDUAL", "displayName": "H"}).data["id"]
    quote = admin_client.post("/api/v1/quotes", {**plan_ref, "proposerId": proposer_id, "effectiveDate": "2026-06-01"}, format="json").data

    missing_reason = admin_client.post(f"/api/v1/quotes/{quote['id']}/cancel", {"rowVersion": 0}, format="json")
    assert missing_reason.status_code == 400
    assert missing_reason.data["code"] == "VALIDATION-400"

    cancelled = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/cancel", {"reasonCode": "CUSTOMER_WITHDREW", "rowVersion": 0}, format="json"
    )
    assert cancelled.status_code == 200
    assert cancelled.data["status"] == "CANCELLED"


@pytest.mark.django_db
def test_cancel_terminal_quote_is_forbidden(admin_client, tenant):
    quote = _approved_quote(admin_client, code_suffix="5", tenant=tenant)

    cancel_approved = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/cancel", {"reasonCode": "TEST", "rowVersion": quote["rowVersion"]}, format="json"
    )
    # APPROVED is cancellable (QT-010) - sanity check the happy path first.
    assert cancel_approved.status_code == 200
    assert cancel_approved.data["status"] == "CANCELLED"

    # A second cancel on the now-CANCELLED (terminal) quote must fail.
    second = admin_client.post(
        f"/api/v1/quotes/{quote['id']}/cancel", {"reasonCode": "TEST", "rowVersion": cancel_approved.data["rowVersion"]}, format="json"
    )
    assert second.status_code == 409
    assert second.data["code"] == "QUOTE-STATE"


class NumberingConcurrencyTest(TransactionTestCase):
    """Q360-S8-02 AC: "Sem duplicação em concorrência" - proven with real
    concurrent threads, not just sequential calls (same pattern already
    established in tests/product for ProductVersion/PricingParameterSet)."""

    def test_concurrent_next_value_never_duplicates(self):
        import uuid as uuid_module

        from apps.foundation.application.context import CurrentActorProvider
        from apps.foundation.domain.actor import Actor
        from apps.foundation.domain.permissions import Role
        from apps.foundation.domain.tenant import TenantId
        from apps.foundation.infrastructure.models import Tenant
        from apps.quote.application.numbering_service import next_value

        tenant = Tenant.objects.create(id=uuid_module.uuid4(), code=f"concurrency-{uuid_module.uuid4().hex[:8]}", name="Concurrency Tenant")
        actor = Actor(actor_id="tester", tenant_id=TenantId(tenant.id), roles=frozenset({Role.ADMIN}))

        results: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(5)

        def worker():
            from django.db import connection

            token = CurrentActorProvider.bind(actor)
            try:
                barrier.wait()
                results.append(next_value(sequence_code="TEST_SEQ", period_key="2026"))
            except Exception as exc:  # pragma: no cover - failure path only
                errors.append(exc)
            finally:
                CurrentActorProvider.reset(token)
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        assert sorted(results) == ["1", "2", "3", "4", "5"]
