"""Public (pre-auth) endpoints for the customer portal login flow —
ROADMAP_PORTAL_CLIENTE.md Fase 0. `tenantId` comes from the URL path (the
portal frontend is deployed per-tenant and always knows its own tenant),
never from a client-asserted body/header field — it is only ever used to
select which tenant's rows a lookup runs against; the actual security
check is still the quoteNumber+registrationNumber(+OTP) match. Namespaced
under `/api/v1/customer-portal/...`, never reusing `/api/v1/quotes` or any
other backoffice path (Fase 0 task list).
"""
from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application.auth_service import CustomerPortalAuthService
from apps.customer_portal.interfaces.rate_limit import is_rate_limited
from apps.customer_portal.interfaces.serializers import (
    PortalTokenResponseSerializer,
    RequestAccessSerializer,
    VerifyOtpSerializer,
)
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.interfaces.middleware import get_correlation_id

_auth_service = CustomerPortalAuthService()


def _bind_anonymous_customer_actor(tenant_id) -> None:
    """Binds just enough of an Actor for `TenantScopedManager`/
    `AuditService` to work during the pre-auth request — never a real
    `customer_account_id` yet (that is what the request is trying to
    resolve). `ActorContextCleanupMiddleware` unbinds it after the
    response regardless."""
    CurrentActorProvider.bind(
        Actor(
            actor_id="anonymous-portal-login",
            tenant_id=TenantId.parse(tenant_id),
            roles=frozenset(),
            scopes=frozenset(),
            actor_type="CUSTOMER",
        )
    )


def _too_many_requests() -> Response:
    return Response(
        {
            "title": "Limite excedido",
            "status": 429,
            "code": "RATE-LIMIT",
            "detail": "Too many login attempts. Try again later.",
            "correlationId": get_correlation_id() or "",
        },
        status=429,
        content_type="application/problem+json",
    )


class RequestAccessView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, tenant_id):
        body = RequestAccessSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        if is_rate_limited(
            tenant_id=str(tenant_id),
            remote_addr=request.META.get("REMOTE_ADDR") or "unknown",
            email=data["email"],
        ):
            return _too_many_requests()

        _bind_anonymous_customer_actor(tenant_id)
        _auth_service.request_access(
            quote_number=data["quoteNumber"],
            registration_number=data["registrationNumber"],
            email=data["email"],
            correlation_id=get_correlation_id(),
        )
        # Always 202, regardless of whether a match was found — see
        # CustomerPortalAuthService.request_access docstring.
        return Response(status=202)


class VerifyOtpView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, tenant_id):
        body = VerifyOtpSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        if is_rate_limited(
            tenant_id=str(tenant_id),
            remote_addr=request.META.get("REMOTE_ADDR") or "unknown",
            email=data["email"],
        ):
            return _too_many_requests()

        _bind_anonymous_customer_actor(tenant_id)
        # InvalidPortalCredentialsError/PortalAccountLockedError propagate
        # to apps.foundation.interfaces.exception_handler.q360_exception_handler
        # unhandled — both are DomainProblem subclasses, handled generically.
        token, ttl_seconds = _auth_service.verify_otp(
            quote_number=data["quoteNumber"],
            registration_number=data["registrationNumber"],
            email=data["email"],
            otp=data["otp"],
            correlation_id=get_correlation_id(),
        )

        response = PortalTokenResponseSerializer({"accessToken": token, "expiresIn": ttl_seconds})
        return Response(response.data, status=200)
