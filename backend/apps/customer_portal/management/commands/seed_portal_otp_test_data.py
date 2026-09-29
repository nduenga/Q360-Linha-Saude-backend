"""Create an active development policy that can authenticate in the customer portal."""
from __future__ import annotations

import datetime
import time
import uuid

import jwt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.client.infrastructure.models import Proposer
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.policy.infrastructure.models import Policy
from apps.pricing.infrastructure.models import RatingTable
from apps.product.infrastructure.models import PricingParameterSet


_STATIC_KEY = "portal-otp-seed-signing-secret-32-bytes"
_TEST_EMAIL = "fabiongila@gmail.com"
_TEST_REGISTRATION_NUMBER = "999999999LA001"


def _client(*, tenant_id: uuid.UUID, roles: list[str], scope: str, actor_id: str) -> APIClient:
    token = jwt.encode(
        {
            "sub": actor_id,
            settings.OIDC_TENANT_CLAIM: str(tenant_id),
            settings.OIDC_ROLES_CLAIM: roles,
            settings.OIDC_SCOPE_CLAIM: scope,
            "exp": int(time.time()) + 300,
        },
        _STATIC_KEY,
        algorithm="HS256",
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    original_post = client.post

    def post_with_idempotency(*args, **kwargs):
        kwargs.setdefault("HTTP_IDEMPOTENCY_KEY", str(uuid.uuid4()))
        kwargs.setdefault("format", "json")
        return original_post(*args, **kwargs)

    client.post = post_with_idempotency
    return client


def _require_success(response, *, action: str):
    if response.status_code >= 400:
        details = getattr(response, "data", response.content.decode(errors="replace"))
        raise CommandError(f"Could not {action}: HTTP {response.status_code} {details}")
    return response.data


class Command(BaseCommand):
    help = "Create or reuse an ACTIVE development policy for customer-portal OTP testing."

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(code="dev-tenant", defaults={"name": "Dev Tenant"})
        self._retire_partial_seed_config(tenant)
        Proposer.all_tenants.filter(
            tenant_id=tenant.id, registration_number=_TEST_REGISTRATION_NUMBER
        ).update(email=_TEST_EMAIL)
        existing = (
            Policy.all_tenants.select_related("proposer")
            .filter(
                tenant_id=tenant.id,
                status="ACTIVE",
                proposer__registration_number=_TEST_REGISTRATION_NUMBER,
            )
            .first()
        )
        if existing:
            self._print_credentials(tenant=tenant, policy=existing)
            return

        original_key = settings.OIDC_STATIC_VERIFICATION_KEY
        original_algorithms = settings.OIDC_ALGORITHMS
        original_allowed_hosts = settings.ALLOWED_HOSTS
        original_jwks_url = settings.OIDC_JWKS_URL
        original_issuer = settings.OIDC_ISSUER
        original_audience = settings.OIDC_AUDIENCE
        original_staff_key = settings.Q360_JWT_SIGNING_KEY
        settings.OIDC_STATIC_VERIFICATION_KEY = _STATIC_KEY
        settings.OIDC_ALGORITHMS = ["HS256"]
        settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "testserver"]
        settings.OIDC_JWKS_URL = ""
        settings.OIDC_ISSUER = ""
        settings.OIDC_AUDIENCE = ""
        settings.Q360_JWT_SIGNING_KEY = ""
        try:
            policy = self._create_active_policy(tenant)
        finally:
            settings.OIDC_STATIC_VERIFICATION_KEY = original_key
            settings.OIDC_ALGORITHMS = original_algorithms
            settings.ALLOWED_HOSTS = original_allowed_hosts
            settings.OIDC_JWKS_URL = original_jwks_url
            settings.OIDC_ISSUER = original_issuer
            settings.OIDC_AUDIENCE = original_audience
            settings.Q360_JWT_SIGNING_KEY = original_staff_key

        self._print_credentials(tenant=tenant, policy=policy)

    @staticmethod
    def _retire_partial_seed_config(tenant: Tenant) -> None:
        RatingTable.all_tenants.filter(
            tenant_id=tenant.id, code__startswith="PORTAL-OTP-TABLE-", status="PUBLISHED"
        ).update(status="RETIRED")
        PricingParameterSet.all_tenants.filter(
            tenant_id=tenant.id, code__startswith="PORTAL-OTP-PARAMS-", status="PUBLISHED"
        ).update(status="RETIRED")
        RuleVersion.all_tenants.filter(
            tenant_id=tenant.id, rule_set__code__startswith="PORTAL-OTP-ELIG-", status="PUBLISHED"
        ).update(status="RETIRED")

    def _create_active_policy(self, tenant: Tenant) -> Policy:
        suffix = uuid.uuid4().hex[:8].upper()
        admin = _client(
            tenant_id=tenant.id,
            roles=["ADMIN"],
            scope="q360.read q360.write q360.admin q360.approve",
            actor_id="portal-otp-seed-admin",
        )
        approver = _client(
            tenant_id=tenant.id,
            roles=["APPROVER"],
            scope="q360.read q360.write q360.approve",
            actor_id="portal-otp-seed-approver",
        )

        product = _require_success(
            admin.post("/api/v1/products", {"code": f"PORTAL-OTP-{suffix}", "name": "Portal OTP Test"}),
            action="create product",
        )
        plan = _require_success(
            admin.post(
                "/api/v1/plans",
                {"productId": product["id"], "code": "BASIC", "name": "Basic"},
            ),
            action="create plan",
        )
        proposer = _require_success(
            admin.post(
                "/api/v1/proposers",
                {
                    "proposerType": "INDIVIDUAL",
                    "displayName": "Portal OTP Tester",
                    "registrationNumber": _TEST_REGISTRATION_NUMBER,
                    "email": _TEST_EMAIL,
                    "phone": "+244900000001",
                },
                format="json",
            ),
            action="create proposer",
        )
        member = _require_success(
            admin.post(
                "/api/v1/members",
                {
                    "proposerId": proposer["id"],
                    "relationshipCode": "TITULAR",
                    "dateOfBirth": "1990-01-01",
                },
                format="json",
            ),
            action="create policy holder",
        )

        today = timezone.localdate()
        quote = _require_success(
            admin.post(
                "/api/v1/quotes",
                {
                    "productId": product["id"],
                    "planId": plan["id"],
                    "proposerId": proposer["id"],
                    "effectiveDate": (today - datetime.timedelta(days=2)).isoformat(),
                },
                format="json",
            ),
            action="create quote",
        )
        _require_success(
            admin.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json"),
            action="add policy holder to quote",
        )
        _require_success(admin.post(f"/api/v1/quotes/{quote['id']}/price"), action="price quote")
        quote = _require_success(admin.get(f"/api/v1/quotes/{quote['id']}"), action="read priced quote")
        quote = _require_success(
            admin.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json"),
            action="submit quote",
        )
        quote = _require_success(
            approver.post(
                f"/api/v1/quotes/{quote['id']}/decision",
                {"decision": "APPROVE", "reasonCode": "PORTAL_OTP_TEST", "rowVersion": quote["rowVersion"]},
                format="json",
            ),
            action="approve quote",
        )
        signed_at = timezone.now() - datetime.timedelta(days=2)
        policy_data = _require_success(
            approver.post(
                f"/api/v1/quotes/{quote['id']}/policy",
                {
                    "signatoryName": "Portal OTP Tester",
                    "signatoryDocumentType": "BI",
                    "signatoryDocumentNumber": _TEST_REGISTRATION_NUMBER,
                    "signatoryCapacity": "TOMADOR",
                    "termMonths": 12,
                    "paymentFrequency": "ANUAL",
                    "signedAt": signed_at.isoformat(),
                    "rowVersion": quote["rowVersion"],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            ),
            action="issue policy",
        )
        policy_data = _require_success(
            approver.post(
                f"/api/v1/policies/{policy_data['id']}/installments/1/payment",
                {
                    "paidAt": (timezone.now() - datetime.timedelta(days=1)).isoformat(),
                    "paymentReference": f"PORTAL-OTP-{suffix}",
                    "paymentMethod": "TEST",
                    "rowVersion": policy_data["rowVersion"],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            ),
            action="register first premium payment",
        )
        return Policy.all_tenants.get(id=policy_data["id"])

    def _print_credentials(self, *, tenant: Tenant, policy: Policy) -> None:
        self.stdout.write(self.style.SUCCESS("Portal OTP test data is ready."))
        self.stdout.write(f"Tenant ID: {tenant.id}")
        self.stdout.write(f"Policy number: {policy.policy_number}")
        self.stdout.write(f"Registration number: {_TEST_REGISTRATION_NUMBER}")
        self.stdout.write(f"Email: {_TEST_EMAIL}")
