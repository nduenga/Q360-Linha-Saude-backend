"""Public (pre-auth) endpoints for the customer portal login flow —
ROADMAP_PORTAL_CLIENTE.md Fase 0, migrated to Policy in Fase 6
(DECISIONS_TAKEN.md#S09-POLICY-001). `tenantId` comes from the URL path
(the portal frontend is deployed per-tenant and always knows its own
tenant), never from a client-asserted body/header field — it is only ever
used to select which tenant's rows a lookup runs against; the actual
security check is still the policyNumber+registrationNumber(+OTP) match.
Namespaced under `/api/v1/customer-portal/...`, never reusing
`/api/v1/policies` or any other backoffice path (Fase 0 task list).
"""
from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from apps.customer_portal.application.auth_service import CustomerPortalAuthService
from apps.customer_portal.application.password_auth_service import CustomerPortalPasswordAuthService
from apps.customer_portal.domain.errors import PortalLegacyLoginDisabledError
from apps.customer_portal.interfaces.rate_limit import is_ip_rate_limited, is_rate_limited
from apps.customer_portal.interfaces.serializers import (
    FirstAccessConfirmSerializer,
    FirstAccessMaskedEmailSerializer,
    FirstAccessRequestSerializer,
    PasswordLoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PortalTokenResponseSerializer,
    RequestAccessSerializer,
    VerifyOtpSerializer,
)
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.interfaces.middleware import get_correlation_id

_auth_service = CustomerPortalAuthService()
_password_service = CustomerPortalPasswordAuthService()


def _require_legacy_login() -> None:
    if not settings.CUSTOMER_PORTAL_LEGACY_LOGIN_ENABLED:
        raise PortalLegacyLoginDisabledError("Este método de início de sessão já não está disponível")


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
            "detail": "Demasiadas tentativas de início de sessão. Tente de novo mais tarde.",
            "correlationId": get_correlation_id() or "",
        },
        status=429,
        content_type="application/problem+json",
    )


class RequestAccessView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, tenant_id):
        _require_legacy_login()
        body = RequestAccessSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        remote_addr = request.META.get("REMOTE_ADDR") or "unknown"

        # Two independent buckets, both must pass: per-email (existing) and
        # per-IP-only (new — email is unverified/attacker-controlled at
        # this point, so a per-email bucket alone is trivially bypassed by
        # varying it on every request; see is_ip_rate_limited docstring).
        if is_rate_limited(
            tenant_id=str(tenant_id), remote_addr=remote_addr, email=data["email"]
        ) or is_ip_rate_limited(tenant_id=str(tenant_id), remote_addr=remote_addr):
            return _too_many_requests()

        _bind_anonymous_customer_actor(tenant_id)
        # Raises PortalPolicyNotFoundError (404) / PortalRegistrationMismatchError
        # (401) if the pair doesn't resolve — Product Owner decision,
        # 2026-09-26 (see CustomerPortalAuthService.request_access docstring).
        _auth_service.request_access(
            policy_number=data["policyNumber"],
            registration_number=data["registrationNumber"],
            email=data["email"],
            correlation_id=get_correlation_id(),
        )
        return Response(status=202)


class VerifyOtpView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, tenant_id):
        _require_legacy_login()
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
            policy_number=data["policyNumber"],
            registration_number=data["registrationNumber"],
            email=data["email"],
            otp=data["otp"],
            correlation_id=get_correlation_id(),
        )

        response = PortalTokenResponseSerializer({"accessToken": token, "expiresIn": ttl_seconds})
        return Response(response.data, status=200)


def _token_response(token: str, ttl_seconds: int) -> Response:
    return Response(PortalTokenResponseSerializer({"accessToken": token, "expiresIn": ttl_seconds}).data, status=200)


def _remote_addr(request) -> str:
    return request.META.get("REMOTE_ADDR") or "unknown"


class _PublicAuthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


class FirstAccessRequestView(_PublicAuthView):
    """Passo 1 do primeiro acesso: o código vai para o email guardado no registo
    do cliente, nunca para um email escrito no pedido."""

    def post(self, request, tenant_id):
        body = FirstAccessRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        # Diz qual dos dois dados está errado (decisão do PO, 2026-09-26), logo
        # o limite por IP é obrigatório, como no pedido de acesso antigo.
        if is_rate_limited(tenant_id=str(tenant_id), remote_addr=_remote_addr(request), email=data["reference"]) or (
            is_ip_rate_limited(tenant_id=str(tenant_id), remote_addr=_remote_addr(request))
        ):
            return _too_many_requests()
        _bind_anonymous_customer_actor(tenant_id)
        masked = _password_service.first_access_request(
            reference=data["reference"], registration_number=data["registrationNumber"],
            correlation_id=get_correlation_id(),
        )
        return Response(FirstAccessMaskedEmailSerializer({"maskedEmail": masked}).data, status=202)


class FirstAccessConfirmView(_PublicAuthView):
    def post(self, request, tenant_id):
        body = FirstAccessConfirmSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if is_rate_limited(tenant_id=str(tenant_id), remote_addr=_remote_addr(request), email=data["reference"]):
            return _too_many_requests()
        _bind_anonymous_customer_actor(tenant_id)
        token, ttl = _password_service.first_access_confirm(
            reference=data["reference"], registration_number=data["registrationNumber"], otp=data["otp"],
            password=data["password"], correlation_id=get_correlation_id(),
        )
        return _token_response(token, ttl)


class PasswordLoginView(_PublicAuthView):
    def post(self, request, tenant_id):
        body = PasswordLoginSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if is_rate_limited(tenant_id=str(tenant_id), remote_addr=_remote_addr(request), email=data["email"].lower()):
            return _too_many_requests()
        _bind_anonymous_customer_actor(tenant_id)
        token, ttl = _password_service.login(
            email=data["email"], password=data["password"], correlation_id=get_correlation_id()
        )
        return _token_response(token, ttl)


class PasswordResetRequestView(_PublicAuthView):
    """Responde sempre 202, exista ou não conta para o email."""

    def post(self, request, tenant_id):
        body = PasswordResetRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if is_rate_limited(tenant_id=str(tenant_id), remote_addr=_remote_addr(request), email=data["email"].lower()):
            return _too_many_requests()
        _bind_anonymous_customer_actor(tenant_id)
        _password_service.password_reset_request(email=data["email"], correlation_id=get_correlation_id())
        return Response(status=202)


class PasswordResetConfirmView(_PublicAuthView):
    def post(self, request, tenant_id):
        body = PasswordResetConfirmSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if is_rate_limited(tenant_id=str(tenant_id), remote_addr=_remote_addr(request), email=data["email"].lower()):
            return _too_many_requests()
        _bind_anonymous_customer_actor(tenant_id)
        token, ttl = _password_service.password_reset_confirm(
            email=data["email"], otp=data["otp"], password=data["password"], correlation_id=get_correlation_id()
        )
        return _token_response(token, ttl)
