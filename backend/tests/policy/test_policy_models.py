"""ROADMAP_APOLICES.md Fase 2 — data-model-only tests (no issuance use
case yet, that is Fase 3): proves the schema/constraints
`0001_policy_baseline.py` declares actually hold, exercised through the
real ORM models against a real Postgres.

Builds a real `Quote` + `QuoteSnapshot` through the existing HTTP API
(same helper pattern as tests/quote/test_quotes.py's `_plan`/`_proposer`)
and then creates `Policy`/`PolicySignature`/`PolicyMember` directly via
`all_tenants.create(...)`, since there is no `apps.policy` service layer
yet (Fase 3).
"""
from __future__ import annotations

import datetime
import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.client.infrastructure.models import InsuredMember
from apps.policy.domain.enums import PolicyMemberStatus, PolicyStatus, PolicyType, SignatoryCapacity, SignatoryDocumentType
from apps.policy.infrastructure.models import Policy, PolicyMember, PolicySignature
from apps.quote.infrastructure.models import Quote, QuoteSnapshot


def _plan(client, *, product_code: str) -> dict:
    product = client.post("/api/v1/products", {"code": product_code, "name": product_code}).data
    plan = client.post("/api/v1/plans", {"productId": product["id"], "code": "BASIC", "name": "Basic"}).data
    return {"productId": product["id"], "planId": plan["id"]}


def _proposer(client, *, registration_number: str = "123456789LA042") -> str:
    return client.post(
        "/api/v1/proposers",
        {
            "proposerType": "INDIVIDUAL",
            "displayName": "Holder",
            "registrationNumber": registration_number,
            "email": "holder@example.com",
            "phone": "+244900000000",
        },
    ).data["id"]


def _quote_with_snapshot(client, *, tenant, suffix: str) -> tuple[Quote, QuoteSnapshot, str]:
    """A DRAFT Quote plus a real QuoteSnapshot (PRICING-typed — good enough
    to satisfy the FK/NOT NULL, since Fase 2 only tests the Policy schema
    itself, not which snapshot type Fase 3's issuance use case picks)."""
    plan_ref = _plan(client, product_code=f"POL-PLAN-{suffix}")
    proposer_id = _proposer(client, registration_number=f"1234567{suffix}LA042"[:14])
    quote_data = client.post(
        "/api/v1/quotes",
        {"proposerId": proposer_id, "planId": plan_ref["planId"], "effectiveDate": "2026-06-01"},
        format="json",
    ).data
    quote = Quote.all_tenants.get(id=quote_data["id"])
    snapshot = QuoteSnapshot.all_tenants.create(
        tenant_id=tenant.id,
        quote=quote,
        snapshot_no=1,
        snapshot_type="APPROVAL",
        plan_id=plan_ref["planId"],
        snapshot_json={"plan": {"planId": plan_ref["planId"]}},
        checksum="test-checksum",
        created_by="actor-1",
    )
    return quote, snapshot, proposer_id


def _member(*, tenant, proposer_id: str) -> InsuredMember:
    return InsuredMember.all_tenants.create(
        tenant_id=tenant.id,
        proposer_id=proposer_id,
        relationship_code="TITULAR",
        first_name="A",
        last_name="B",
        date_of_birth=datetime.date(1990, 1, 1),
    )


def _issue_policy(*, tenant, quote, snapshot, proposer_id, **overrides) -> Policy:
    fields = dict(
        tenant_id=tenant.id,
        policy_number=f"APO-{uuid.uuid4().hex[:8]}",
        source_quote=quote,
        contracted_terms_snapshot=snapshot,
        proposer_id=proposer_id,
        plan_id=snapshot.plan_id,
        policy_type=PolicyType.INDIVIDUAL.value,
        term_months=12,
        status=PolicyStatus.PENDING_FIRST_PREMIUM.value,
        payment_frequency="ANUAL",
        currency_code="AOA",
        issued_by="actor-1",
    )
    fields.update(overrides)
    return Policy.all_tenants.create(**fields)


@pytest.mark.django_db
def test_issue_policy_from_quote_and_snapshot(admin_client, tenant):
    quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="1")
    policy = _issue_policy(tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id)

    assert policy.status == PolicyStatus.PENDING_FIRST_PREMIUM.value
    assert policy.start_date is None and policy.end_date is None
    assert policy.row_version == 0


@pytest.mark.django_db
def test_a_quote_can_only_produce_one_policy(admin_client, tenant):
    """`uq_policy_source_quote` — PO-APO-1: a signed Quote is bound once."""
    quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="2")
    _issue_policy(tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _issue_policy(tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id)


@pytest.mark.django_db
def test_policy_number_is_unique_per_tenant(admin_client, tenant):
    quote_a, snapshot_a, proposer_a = _quote_with_snapshot(admin_client, tenant=tenant, suffix="3a")
    quote_b, snapshot_b, proposer_b = _quote_with_snapshot(admin_client, tenant=tenant, suffix="3b")
    _issue_policy(
        tenant=tenant, quote=quote_a, snapshot=snapshot_a, proposer_id=proposer_a, policy_number="APO-DUP"
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _issue_policy(
                tenant=tenant, quote=quote_b, snapshot=snapshot_b, proposer_id=proposer_b, policy_number="APO-DUP"
            )


@pytest.mark.django_db
def test_invalid_status_is_rejected_by_the_database(admin_client, tenant):
    quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="4")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _issue_policy(tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id, status="MADE_UP")


@pytest.mark.django_db
def test_end_date_before_start_date_is_rejected(admin_client, tenant):
    """`ck_policy_dates` — no retroactive/inverted vigência."""
    quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="5")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _issue_policy(
                tenant=tenant,
                quote=quote,
                snapshot=snapshot,
                proposer_id=proposer_id,
                status=PolicyStatus.ACTIVE.value,
                start_date=datetime.date(2026, 6, 10),
                end_date=datetime.date(2026, 6, 1),
            )


@pytest.mark.django_db
def test_one_signature_per_policy(admin_client, tenant):
    quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="6")
    policy = _issue_policy(tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id)

    PolicySignature.all_tenants.create(
        tenant_id=tenant.id,
        policy=policy,
        signatory_name="Holder",
        signatory_document_type=SignatoryDocumentType.BI.value,
        signatory_document_number="000000000BI000",
        signatory_capacity=SignatoryCapacity.TOMADOR.value,
        signed_at=datetime.datetime(2026, 6, 1, 14, 0, tzinfo=datetime.timezone.utc),
        registered_by="actor-1",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PolicySignature.all_tenants.create(
                tenant_id=tenant.id,
                policy=policy,
                signatory_name="Holder Again",
                signatory_document_type=SignatoryDocumentType.BI.value,
                signatory_document_number="111111111BI111",
                signatory_capacity=SignatoryCapacity.TOMADOR.value,
                signed_at=datetime.datetime(2026, 6, 1, 15, 0, tzinfo=datetime.timezone.utc),
                registered_by="actor-1",
            )


@pytest.mark.django_db
def test_policy_member_unique_per_policy(admin_client, tenant):
    quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="7")
    policy = _issue_policy(tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id)
    member = _member(tenant=tenant, proposer_id=proposer_id)

    PolicyMember.all_tenants.create(
        tenant_id=tenant.id, policy=policy, member=member, status=PolicyMemberStatus.PENDING.value
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PolicyMember.all_tenants.create(
                tenant_id=tenant.id, policy=policy, member=member, status=PolicyMemberStatus.ACTIVE.value
            )


@pytest.mark.django_db
def test_policy_member_pending_never_blocks_the_others(admin_client, tenant):
    """PO-APO-2: a pending member is just a row with its own status — no
    schema-level coupling forces the whole Policy to reflect it."""
    quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="8")
    policy = _issue_policy(
        tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id, status=PolicyStatus.ACTIVE.value,
        start_date=datetime.date(2026, 6, 2), end_date=datetime.date(2027, 6, 1),
    )
    pending_member = _member(tenant=tenant, proposer_id=proposer_id)
    active_member = _member(tenant=tenant, proposer_id=proposer_id)

    PolicyMember.all_tenants.create(
        tenant_id=tenant.id,
        policy=policy,
        member=pending_member,
        status=PolicyMemberStatus.PENDING.value,
        pending_reason_code="FALTA_CERTIFICADO_MATRICULA",
    )
    PolicyMember.all_tenants.create(
        tenant_id=tenant.id,
        policy=policy,
        member=active_member,
        status=PolicyMemberStatus.ACTIVE.value,
        inclusion_date=policy.start_date,
    )

    assert policy.status == PolicyStatus.ACTIVE.value
    statuses = set(PolicyMember.all_tenants.filter(policy=policy).values_list("status", flat=True))
    assert statuses == {PolicyMemberStatus.PENDING.value, PolicyMemberStatus.ACTIVE.value}


@pytest.mark.django_db
class TestPolicyTenantIsolation:
    def test_cross_tenant_policy_is_not_visible_via_objects_manager(self, admin_client, tenant):
        from apps.foundation.application.context import CurrentActorProvider
        from apps.foundation.domain.actor import Actor
        from apps.foundation.domain.permissions import Role
        from apps.foundation.domain.tenant import TenantId
        from apps.foundation.infrastructure.models import Tenant

        quote, snapshot, proposer_id = _quote_with_snapshot(admin_client, tenant=tenant, suffix="9")
        _issue_policy(tenant=tenant, quote=quote, snapshot=snapshot, proposer_id=proposer_id)

        other_tenant = Tenant.objects.create(id=uuid.uuid4(), code=f"other-{uuid.uuid4().hex[:8]}", name="Other")
        other_actor = Actor(
            actor_id="other-actor", tenant_id=TenantId(other_tenant.id), roles=frozenset({Role.ADMIN})
        )

        token = CurrentActorProvider.bind(other_actor)
        try:
            assert Policy.objects.count() == 0
        finally:
            CurrentActorProvider.reset(token)
