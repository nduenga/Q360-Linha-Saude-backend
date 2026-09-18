"""TENANT-001 … TENANT-017: Tenant isolation contract tests.

All entity-bearing endpoints must:
  * List: return only the caller's tenant's rows.
  * Get by ID: return 404 (not 403) for another tenant's entity.

Per DOC-001 s20 — endpoints must never confirm existence of another
tenant's data to a caller.
"""
from __future__ import annotations

import json
import time
import uuid

import jwt
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.foundation.infrastructure.models import Tenant

_SECRET = "tenant-iso-signing-secret-32-bytes-min-xxx"


@pytest.fixture(autouse=True)
def _oidc_static_key(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = _SECRET
    settings.OIDC_ALGORITHMS = ["HS256"]


def _make_tenant(*, suffix: str = "") -> Tenant:
    return Tenant.objects.create(
        id=uuid.uuid4(), code=f"tenant{suffix}-{uuid.uuid4().hex[:8]}", name=f"Tenant {suffix}"
    )


def _token(*, tenant_id, roles: list[str], scope: str, actor_id: str = "actor-1") -> str:
    claims = {
        "sub": actor_id,
        "tenant_id": str(tenant_id),
        "roles": roles,
        "scope": scope,
        "exp": int(time.time()) + 300,
    }
    return jwt.encode(claims, _SECRET, algorithm="HS256")


def make_client(*, tenant_id, roles: list[str], scope: str, actor_id: str = "actor-1") -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {_token(tenant_id=tenant_id, roles=roles, scope=scope, actor_id=actor_id)}")
    return client


@pytest.mark.django_db
class TestProductTenantIsolation:
    """TENANT-001 … TENANT-003: Product / ProductVersion / Plan."""

    def test_TENANT_001_cross_tenant_product_is_404_not_403(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        created = owner.post("/api/v1/products", {"code": "X", "name": "Secret"}).data

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/products/{created['id']}")
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT-FOUND"

    def test_TENANT_002_cross_tenant_products_not_listed(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        owner.post("/api/v1/products", {"code": "MINE", "name": "Mine"})

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get("/api/v1/products")
        assert resp.status_code == 200
        assert resp.data["items"] == []

    def test_TENANT_003_cross_tenant_plan_is_404_not_403(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        product = owner.post("/api/v1/products", {"code": "P", "name": "P"}).data
        version = owner.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}).data
        plan = owner.post(
            "/api/v1/plans",
            {"productVersionId": version["id"], "code": "BASE", "name": "Base Plan"},
        ).data

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/plans/{plan['id']}")
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT-FOUND"


@pytest.mark.django_db
class TestClientTenantIsolation:
    """TENANT-004 … TENANT-006: Proposer / InsuredMember."""

    def _make_proposer(self, client):
        return client.post(
            "/api/v1/proposers",
            {
                "proposerType": "INDIVIDUAL",
                "displayName": "Maria Silva",
                "registrationNumber": f"doc-{uuid.uuid4().hex[:8]}",
                "attributes": {"email": "maria@example.com"},
            },
        ).data

    def test_TENANT_004_cross_tenant_proposer_is_404_not_403(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write")
        proposer = self._make_proposer(owner)

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/proposers/{proposer['id']}")
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT-FOUND"

    def test_TENANT_005_cross_tenant_proposers_not_listed(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write")
        self._make_proposer(owner)

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get("/api/v1/proposers")
        assert resp.status_code == 200
        assert resp.data["items"] == []

    def test_TENANT_006_cross_tenant_member_is_404_not_403(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write")
        proposer = self._make_proposer(owner)
        member = owner.post(
            "/api/v1/members",
            {
                "firstName": "João",
                "lastName": "Silva",
                "relationshipCode": "SPOUSE",
                "dateOfBirth": "1981-03-03",
                "proposerId": proposer["id"],
                "attributes": {"smoker": False},
            },
        ).data

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/members/{member['id']}")
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT-FOUND"


@pytest.mark.django_db
class TestConfigTenantIsolation:
    """TENANT-007 … TENANT-010: RuleVersion / PricingParameterSet / RatingTable / AuditEvent."""

    def test_TENANT_007_cross_tenant_rule_version_not_listed(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.admin")
        owner.post(
            "/api/v1/rule-versions",
            {
                "ruleSetCode": "ELIGIBILITY-DEFAULT",
                "ruleDomain": "ELIGIBILITY",
                "effectiveFrom": "2026-01-01",
                "rules": {
                    "version": 1,
                    "expressions": [{"id": "e1", "expression": "age_band == 'ADULT'", "reason": "adult required"}],
                },
            },
        )

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get("/api/v1/rule-versions")
        assert resp.status_code == 200
        assert resp.data["items"] == []

    def test_TENANT_008_cross_tenant_pricing_parameter_set_not_listed(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        product = owner.post("/api/v1/products", {"code": "PP", "name": "PP"}).data
        version = owner.post(f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}).data
        owner.post(
            f"/api/v1/products/{product['id']}/versions/{version['id']}/pricing-parameter-sets",
            {
                "parameterSetCode": "PPS",
                "name": "My Params",
                "currencyCode": "BRL",
                "decimalParameters": [],
                "ratingTableParameters": [],
            },
        )

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/products/{product['id']}/versions/{version['id']}/pricing-parameter-sets")
        # Cross-tenant should not even see the product version → 404 on the path's parent
        assert resp.status_code == 404

    def test_TENANT_009_cross_tenant_rating_table_not_listed(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.admin")
        owner.post(
            "/api/v1/rating-tables",
            {
                "code": "RT-A",
                "name": "Rating A",
                "effectiveFrom": "2026-01-01",
                "currencyCode": "BRL",
                "factors": [
                    {"rowKey": "ADULT|MALE", "factorValue": "1.000"},
                    {"rowKey": "ADULT|FEMALE", "factorValue": "0.900"},
                ],
            },
        )

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get("/api/v1/rating-tables")
        assert resp.status_code == 200
        assert resp.data["items"] == []

    def test_TENANT_010_cross_tenant_audit_events_not_listed(self, db):
        from apps.foundation.infrastructure.models import AuditEvent

        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        AuditEvent.all_tenants.create(
            id=uuid.uuid4(),
            tenant_id=t1.id,
            action="quote.created",
            actor_id="actor-1",
            correlation_id=f"corr-{uuid.uuid4().hex}",
            entity_type="Quote",
            entity_id=str(uuid.uuid4()),
            metadata_json={},
        )

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read q360.audit")
        resp = other.get("/api/v1/audit-events")
        assert resp.status_code == 200
        assert resp.data["items"] == []


@pytest.mark.django_db
class TestQuotePricingEligibilityTenantIsolation:
    """TENANT-011 … TENANT-017: Quote, Pricing, Eligibility, Documents."""

    def _make_product_and_plan(self, admin_client):
        suffix = uuid.uuid4().hex[:8]
        product = admin_client.post("/api/v1/products", {"code": f"QP-{suffix}", "name": "QP"}).data
        version = admin_client.post(
            f"/api/v1/products/{product['id']}/versions", {"effectiveFrom": "2026-01-01"}
        ).data
        plan = admin_client.post(
            "/api/v1/plans",
            {"productVersionId": version["id"], "code": "B", "name": "B"},
        ).data
        rule = admin_client.post(
            "/api/v1/rule-versions",
            {
                "code": f"ELIG-{suffix}",
                "name": "Eligibility default",
                "ruleDomain": "ELIGIBILITY",
                "effectiveFrom": "2026-01-01",
                "artifactType": "JSON",
                "artifactRef": json.dumps({}),
            },
        ).data
        admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
        params = admin_client.post(
            "/api/v1/pricing-parameter-sets",
            {
                "code": f"PARAMS-{suffix}",
                "name": "Default",
                "effectiveFrom": "2026-01-01",
                "parameters": [
                    {"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "100.00"},
                ],
            },
        ).data
        admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{params['id']}/publish")
        table = admin_client.post(
            "/api/v1/rating-tables",
            {
                "code": f"TABLE-{suffix}", "name": "t", "effectiveFrom": "2026-01-01", "currencyCode": "BRL",
                "factors": [{"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00"}],
            },
        ).data
        admin_client.post(f"/api/v1/configuration/rating-table/{table['id']}/publish")
        admin_client.post(f"/api/v1/product-versions/{version['id']}/publish")
        from apps.product.infrastructure.models import Plan, ProductVersion

        return product, ProductVersion.all_tenants.get(id=version["id"]), Plan.all_tenants.get(id=plan["id"])

    def _make_proposer_and_principal_member(self, admin_client):
        from apps.client.infrastructure.models import InsuredMember, Proposer

        tenant = admin_client.handler._force_tenant_hack if hasattr(admin_client.handler, "_force_tenant_hack") else None
        if not tenant:
            # Parse tenant from token in credentials
            from django.conf import settings

            auth_header = admin_client._credentials["HTTP_AUTHORIZATION"]
            token = auth_header.split(" ")[1]
            claims = jwt.decode(token, settings.OIDC_STATIC_VERIFICATION_KEY, algorithms=settings.OIDC_ALGORITHMS, audience=None)
            tenant_id = claims["tenant_id"]
        else:
            tenant_id = str(tenant.id)

        proposer = Proposer.all_tenants.create(
            tenant_id=tenant_id,
            proposer_type="INDIVIDUAL",
            external_reference=f"prp-{uuid.uuid4().hex[:8]}",
            display_name="Ana Costa",
            registration_number="12345678900",
            attributes_json={
                "email": "ana@example.com",
                "phoneCountry": "55",
                "phoneNumber": "11988887777",
                "addressLine1": "Rua B",
                "city": "Rio",
                "subdivisionCode": "RJ",
                "postalCode": "22041001",
                "countryCode": "BR",
            },
        )
        member = InsuredMember.all_tenants.create(
            tenant_id=tenant_id,
            proposer_id=proposer.id,
            external_reference=f"mbr-{uuid.uuid4().hex[:8]}",
            relationship_code="PRINCIPAL",
            first_name="Ana",
            last_name="Costa",
            date_of_birth="1985-05-05",
            sex_code="FEMALE",
            attributes_json={"smoker": False},
        )
        return proposer, member

    def test_TENANT_011_cross_tenant_quote_is_404_not_403(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        _, version, plan = self._make_product_and_plan(owner)
        proposer, member = self._make_proposer_and_principal_member(owner)
        quote = owner.post(
            "/api/v1/quotes",
            {"proposerId": str(proposer.id), "productVersionId": "placeholder", "planId": "placeholder", "effectiveDate": "2026-06-01"},
        )
        # We don't need a successful quote creation — as long as we have a quote ID,
        # we can test cross-tenant visibility. Let's bypass the request and create directly.
        from apps.quote.infrastructure.models import Quote

        real_quote = Quote.all_tenants.create(
            tenant_id=t1.id,
            proposer=proposer,
            product_version=version,
            plan=plan,
            effective_date="2026-06-01",
            status="DRAFT",
        )

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/quotes/{real_quote.id}")
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT-FOUND"

    def test_TENANT_012_cross_tenant_quotes_not_listed(self, db):
        from apps.quote.infrastructure.models import Quote

        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        _, version, plan = self._make_product_and_plan(owner)
        proposer, _ = self._make_proposer_and_principal_member(owner)
        Quote.all_tenants.create(
            tenant_id=t1.id,
            proposer=proposer,
            product_version=version,
            plan=plan,
            effective_date="2026-06-01",
            status="DRAFT",
        )

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get("/api/v1/quotes")
        assert resp.status_code == 200
        assert resp.data["items"] == []

    def test_TENANT_013_cross_tenant_pricing_run_explanation_404(self, db):
        from apps.pricing.infrastructure.models import PricingRun, RatingTable
        from apps.product.infrastructure.models import PricingParameterSet

        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        _, version, plan = self._make_product_and_plan(owner)
        rating_table = RatingTable.all_tenants.create(
            tenant_id=t1.id, code="RT", name="RT", version_no=1,
            effective_from="2026-01-01", currency_code="BRL",
        )
        parameter_set = PricingParameterSet.all_tenants.create(
            tenant_id=t1.id, code="PS", version_no=1, effective_from="2026-01-01",
        )
        run = PricingRun.all_tenants.create(
            tenant_id=t1.id,
            product_version=version,
            plan=plan,
            rating_table=rating_table,
            parameter_set=parameter_set,
            effective_date="2026-06-01",
            currency_code="BRL",
            rounding_policy_code="TEST",
            rounding_policy_version=1,
            input_snapshot_json={},
            status="CALCULATED",
            total_amount="100.00",
            completed_at=timezone.now(),
        )

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/pricing/{run.id}/explanation")
        assert resp.status_code == 404

    def test_TENANT_014_cross_tenant_eligibility_evaluate_rejects_foreign_references(self, db):
        """ART-006 `evaluateEligibility` has no listing endpoint at all
        (only `POST /eligibility/evaluate`), so isolation is exercised by
        proving a tenant cannot reference another tenant's productVersion/
        plan: `EvaluateEligibilityUseCase` resolves both via the tenant-
        scoped manager, so a foreign id resolves to nothing and the use
        case raises ReferencedEntityNotFoundError (400 VALIDATION-400) —
        never evaluates against, or leaks the existence of, tenant A's
        configuration."""
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        _, version, plan = self._make_product_and_plan(owner)

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read q360.write")
        resp = other.post(
            "/api/v1/eligibility/evaluate",
            {
                "proposerId": None,
                "memberId": None,
                "productVersionId": str(version.id),
                "planId": str(plan.id),
                "effectiveDate": "2026-06-01",
                "context": {},
            },
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION-400"

    def _make_approved_quote_with_document(self, admin_client, *, tenant):
        """ART-006 only exposes documents through
        `/quotes/{quoteId}/proposal` — there is no standalone `/documents`
        listing/detail endpoint, so isolation is exercised through that
        real endpoint rather than an invented one."""
        from apps.quote.infrastructure.models import Document, DocumentTemplateVersion, Quote, QuoteSnapshot
        from apps.quote.domain.enums import DocumentStatus, DocumentTemplateStatus, DocumentType

        proposer, _ = self._make_proposer_and_principal_member(admin_client)
        _, version, plan = self._make_product_and_plan(admin_client)
        quote = Quote.all_tenants.create(
            tenant_id=tenant.id,
            proposer=proposer,
            product_version=version,
            plan=plan,
            effective_date="2026-06-01",
            status="APPROVED",
        )
        snapshot = QuoteSnapshot.all_tenants.create(
            tenant_id=tenant.id,
            quote=quote,
            snapshot_no=1,
            snapshot_type="SUBMISSION",
            product_version=version,
            plan=plan,
            snapshot_json={},
            checksum="snap-checksum",
            created_by="actor-1",
        )
        template = DocumentTemplateVersion.all_tenants.create(
            tenant_id=tenant.id,
            template_code="QUOTE_PROPOSAL_DEFAULT",
            version_no=1,
            status=DocumentTemplateStatus.PUBLISHED.value,
            storage_ref="internal://placeholder",
            checksum="tpl-checksum",
            effective_from="2026-01-01",
        )
        doc = Document.all_tenants.create(
            tenant_id=tenant.id,
            quote=quote,
            snapshot=snapshot,
            template_version=template,
            document_type=DocumentType.QUOTE_PROPOSAL.value,
            status=DocumentStatus.GENERATED.value,
            document_number="PROP-001",
            storage_ref="/tmp/x.json",
            checksum="abc",
            requested_by="actor-1",
            generated_at=timezone.now(),
        )
        return quote, doc

    def test_TENANT_015_cross_tenant_document_is_404_not_403(self, db):
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        quote, _doc = self._make_approved_quote_with_document(owner, tenant=t1)

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/quotes/{quote.id}/proposal")
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT-FOUND"

    def test_TENANT_016_cross_tenant_quote_members_not_listed(self, db):
        """Q360-S06 pragmatic addition `GET /quotes/{quoteId}/members`
        (DECISIONS_TAKEN.md#S06-QUOTE-001) must 404 for another tenant,
        matching the AC-8 example in .trae/specs/s09-s11-restantes/spec.md."""
        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        quote, _doc = self._make_approved_quote_with_document(owner, tenant=t1)

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read")
        resp = other.get(f"/api/v1/quotes/{quote.id}/members")
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT-FOUND"

    def test_TENANT_017_cross_tenant_review_task_not_listed(self, db):
        from apps.quote.infrastructure.models import Quote, ReviewTask
        from apps.quote.domain.enums import QuoteStatus

        t1 = _make_tenant(suffix="A")
        t2 = _make_tenant(suffix="B")
        owner = make_client(tenant_id=t1.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
        proposer, _ = self._make_proposer_and_principal_member(owner)
        _, version, plan = self._make_product_and_plan(owner)
        quote = Quote.all_tenants.create(
            tenant_id=t1.id,
            proposer=proposer,
            product_version=version,
            plan=plan,
            effective_date="2026-06-01",
            status=QuoteStatus.IN_REVIEW.value,
        )
        ReviewTask.all_tenants.create(tenant_id=t1.id, quote=quote, created_by="actor-1")

        other = make_client(tenant_id=t2.id, roles=["ADMIN"], scope="q360.read q360.approve")
        resp = other.get("/api/v1/reviews")
        assert resp.status_code == 200
        assert resp.data["items"] == []
